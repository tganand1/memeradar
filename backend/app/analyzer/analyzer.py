from __future__ import annotations

import difflib
import logging
import random
from typing import Any, Awaitable, Callable

from app.analyzer.checks import (
    build_demo_checks,
    bundle_score,
    creator_score,
    holders_score,
    liquidity_score,
    lp_score,
    metadata_score,
    mk_check,
    mk_metric,
    rugcheck_score,
)
from app.analyzer.clients import MarketClients
from app.analyzer.scoring import score_token
from app.analyzer.types import Analysis, NewToken
from app.config import AppConfig
from app.utils import clamp, safe_float, short_addr

log = logging.getLogger("memeradar.analyzer")


class Analyzer:
    def __init__(
        self,
        clients: MarketClients,
        config_getter: Callable[[], AppConfig],
        log_cb: Callable[[str, str, str], Awaitable[None]] | None = None,
    ) -> None:
        self.clients = clients
        self.get_config = config_getter
        self.log_cb = log_cb
        self._known_names: list[tuple[str, str]] = []
        self._known_images: set[str] = set()

    async def _log(self, level: str, message: str) -> None:
        if self.log_cb:
            await self.log_cb(level, "analyzer", message)

    def register_known(self, name: str, symbol: str, image_url: str | None = None) -> None:
        if name:
            self._known_names.append((name.lower(), symbol.lower()))
            if len(self._known_names) > 5000:
                self._known_names = self._known_names[-2500:]
        if image_url:
            self._known_images.add(image_url)

    def load_known(self, names: list[tuple[str, str, str | None]]) -> None:
        for name, symbol, image in names:
            self.register_known(name, symbol, image)

    def _is_copycat(self, name: str) -> bool:
        target = name.lower().strip()
        if not target:
            return False
        for known, _symbol in self._known_names[-1500:]:
            if known == target:
                continue
            if abs(len(known) - len(target)) > 6:
                continue
            if difflib.SequenceMatcher(None, target, known).ratio() >= 0.87:
                return True
        return False

    async def analyze(self, token: NewToken) -> Analysis:
        config = self.get_config()
        try:
            if token.is_demo:
                checks, opp, hard, latent = self._demo_checks(token, config)
            else:
                checks, opp, hard, latent = await self._live_checks(token)
            scores = score_token(checks, opp, config.strategy, hard)
            analysis = Analysis(
                checks=checks,
                opportunity_metrics=opp,
                hard_data=hard,
                scores=scores,
                archetype=token.archetype or "live",
                quality=float(latent.get("quality", 0.0)),
                rug_probability=float(latent.get("rug_probability", 0.1)),
                drift=float(latent.get("drift", 0.0)),
                volatility=float(latent.get("volatility", 0.03)),
            )
            return analysis
        except Exception as exc:
            log.exception("Analyzer failure for %s", token.mint)
            await self._log("error", f"Analyzer failed for {token.symbol}: {exc}")
            return self._fallback_analysis(token, str(exc))

    def _demo_checks(self, token: NewToken, config: AppConfig) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
        profile = token.demo_profile or {}
        if profile.get("checks"):
            return profile["checks"], profile["opportunity"], profile["hard"], profile["latent"]
        rng = random.Random(f"{token.mint}-{token.created_at.isoformat()}")
        archetype = token.archetype or rng.choices(
            ["gem", "solid", "risky", "scam"], weights=[18, 30, 32, 20], k=1
        )[0]
        token.archetype = archetype
        return build_demo_checks(archetype, rng, token.market_cap_usd, token.liquidity_usd, token.price_usd)

    async def _live_checks(
        self, token: NewToken
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
        mint = token.mint
        pair, mint_info, summary, report, creator_assets, sell_ok = await self._collect_live_data(mint, token.creator)
        risks = self._risk_names(summary, report)
        info = (pair or {}).get("info") or {}

        liquidity = safe_float(((pair or {}).get("liquidity") or {}).get("usd"), token.liquidity_usd)
        price = safe_float((pair or {}).get("priceUsd"), token.price_usd)
        mcap = safe_float((pair or {}).get("marketCap"), token.market_cap_usd)
        if mcap <= 0:
            mcap = safe_float((pair or {}).get("fdv"), token.market_cap_usd)

        checks: dict[str, Any] = {}

        mint_authority = None
        freeze_authority = None
        if mint_info is not None:
            mint_authority = mint_info.get("mintAuthority")
            freeze_authority = mint_info.get("freezeAuthority")
        mint_revoked: bool | None = None if mint_info is None else mint_authority is None
        freeze_revoked: bool | None = None if mint_info is None else freeze_authority is None
        checks["mint_authority"] = mk_check(
            "mint_authority",
            "Mint authority revoked",
            1.0 if mint_revoked else (0.25 if mint_revoked is None else 0.0),
            bool(mint_revoked),
            "Revoked" if mint_revoked else ("UNVERIFIED" if mint_revoked is None else "ACTIVE"),
            "Mint authority is renounced."
            if mint_revoked
            else ("Could not verify mint authority (RPC unavailable)." if mint_revoked is None else "Mint authority is active."),
            critical=True,
            data={"authority": mint_authority if mint_authority else None, "verified": mint_info is not None},
        )
        checks["freeze_authority"] = mk_check(
            "freeze_authority",
            "Freeze authority revoked",
            1.0 if freeze_revoked else (0.25 if freeze_revoked is None else 0.0),
            bool(freeze_revoked),
            "Revoked" if freeze_revoked else ("UNVERIFIED" if freeze_revoked is None else "ACTIVE"),
            "Freeze authority is renounced."
            if freeze_revoked
            else ("Could not verify freeze authority (RPC unavailable)." if freeze_revoked is None else "Freeze authority active."),
            critical=True,
            data={"authority": freeze_authority if freeze_authority else None, "verified": mint_info is not None},
        )

        checks["liquidity"] = mk_check(
            "liquidity",
            "Liquidity depth",
            liquidity_score(liquidity),
            liquidity >= self.get_config().strategy.hard_reject.min_liquidity_usd,
            f"${liquidity:,.0f}",
            f"${liquidity:,.0f} pool liquidity across the deepest Solana pair.",
            data={"usd": round(liquidity, 2), "mcap_liq_ratio": round(mcap / liquidity, 2) if liquidity else None},
        )

        lp_data = self._lp_data(report, risks)
        checks["lp_lock"] = mk_check(
            "lp_lock",
            "LP burned / locked",
            lp_score(lp_data["burned"], lp_data["locked_days"]),
            lp_data["burned"] or lp_data["locked_days"] >= 7,
            "Burned" if lp_data["burned"] else (f"Locked {lp_data['locked_days']}d" if lp_data["locked_days"] else "Unknown/unlocked"),
            lp_data["detail"],
            data=lp_data,
        )

        holders = self._holders_data(report)
        top10_pct = safe_float(holders.get("top10_pct"))
        top1_pct = safe_float(holders.get("top1_pct"))
        holder_count = int(safe_float(holders.get("count")))
        holders_verified = bool(holders.get("verified"))
        checks["holders"] = mk_check(
            "holders",
            "Holder distribution",
            holders_score(top10_pct, top1_pct, holder_count) if holders_verified else 0.25,
            holders_verified and top10_pct < 35 and holder_count >= self.get_config().strategy.hard_reject.min_holders,
            f"top10 {top10_pct:.1f}%" if holders_verified else "Unverified",
            (
                f"{holder_count} holders; top wallet {top1_pct:.1f}%, top 10 hold {top10_pct:.1f}% (best-effort pool exclusion)."
                if holders_verified
                else "Holder distribution unavailable from RugCheck."
            ),
            data=holders,
        )

        creator = self._creator_data(report, risks, creator_assets, token.creator)
        checks["creator"] = mk_check(
            "creator",
            "Creator wallet history",
            creator_score(int(creator["previous_rugs"]), int(creator["tokens_launched"]), float(creator["holds_pct"])),
            int(creator["previous_rugs"]) < 3 and float(creator["holds_pct"]) < 10,
            f"{creator['previous_rugs']} prior rugs (est.)",
            f"Creator {short_addr(creator.get('wallet'))} launched {creator['tokens_launched']} token(s); "
            f"{creator['previous_rugs']} rug signal(s); holds {creator['holds_pct']:.1f}%.",
            data=creator,
        )

        bundle = self._bundle_data(summary, report, risks, top10_pct)
        checks["bundle"] = mk_check(
            "bundle",
            "Bundle / sniper detection",
            bundle_score(float(bundle["cluster_pct"]), int(bundle["sniper_wallets"]), bool(bundle["available"])),
            bool(bundle["available"]) and float(bundle["cluster_pct"]) < 15,
            f"{bundle['cluster_pct']:.1f}% clustered" if bundle["available"] else "Unavailable",
            (
                f"{bundle['sniper_wallets']} sniper signal(s); cluster holds ~{bundle['cluster_pct']:.1f}% (RugCheck heuristics)."
                if bundle["available"]
                else "No bundle data source available; treated as neutral risk."
            ),
            data=bundle,
        )

        honeypot = self._honeypot_data(sell_ok, risks)
        checks["honeypot"] = mk_check(
            "honeypot",
            "Honeypot / sell-ability",
            0.0 if honeypot["detected"] else (0.5 if honeypot["detected"] is None else 1.0),
            honeypot["detected"] is False,
            "FAILED" if honeypot["detected"] else ("Unverified" if honeypot["detected"] is None else "Can sell"),
            honeypot["detail"],
            critical=True,
            data=honeypot,
        )

        rc_score = safe_float((summary or {}).get("score_normalised"), safe_float((report or {}).get("score_normalised")))
        checks["rugcheck"] = mk_check(
            "rugcheck",
            "RugCheck.xyz risk",
            rugcheck_score(rc_score, len(risks)) if summary or report else 0.3,
            rc_score >= 60 and not risks,
            f"{rc_score:.0f}/100" if summary or report else "Unavailable",
            f"RugCheck normalised safety {rc_score:.0f}/100; {len(risks)} risk flag(s)." if summary or report else "RugCheck unavailable.",
            data={"score": round(rc_score, 1), "risks": risks, "available": bool(summary or report)},
        )

        socials = [s.get("type", "link") for s in info.get("socials") or [] if isinstance(s, dict)]
        websites = [w.get("url") for w in info.get("websites") or [] if isinstance(w, dict)]
        image = info.get("imageUrl") or token.image_url
        social_count = len(set(socials)) + (1 if websites else 0)
        duplicate_image = bool(image and image in self._known_images)
        copycat = self._is_copycat(token.name)
        checks["metadata"] = mk_check(
            "metadata",
            "Metadata & socials",
            metadata_score(social_count, duplicate_image, copycat),
            social_count >= 1 and not duplicate_image and not copycat,
            f"{social_count} link(s)",
            f"Official links: {', '.join(sorted(set(socials)) + (['website'] if websites else [])) or 'none'}."
            + (" Image duplicated." if duplicate_image else "")
            + (" Copycat name." if copycat else ""),
            data={
                "social_count": social_count,
                "socials": sorted(set(socials)),
                "website": websites[0] if websites else token.website,
                "duplicate_image": duplicate_image,
                "copycat": copycat,
            },
        )

        txns = (pair or {}).get("txns") or {}
        volume = (pair or {}).get("volume") or {}
        change = (pair or {}).get("priceChange") or {}
        window = "m5" if txns.get("m5") else ("h1" if txns.get("h1") else "h6")
        buys = safe_float((txns.get(window) or {}).get("buys"))
        sells = safe_float((txns.get(window) or {}).get("sells"))
        buy_sell = buys / max(sells, 1.0)
        volume_usd = safe_float(volume.get(window), safe_float(volume.get("h1")))
        vol_liq = volume_usd / liquidity if liquidity > 0 else 0.0
        change5 = safe_float(change.get("m5"), safe_float(change.get("h1")))
        unique_buyers = int(buys)
        wash = 0.3
        mcap_liq = mcap / liquidity if liquidity > 0 else 99.0

        checks["trading"] = mk_check(
            "trading",
            "Early trading behaviour",
            clamp(
                0.4 * clamp((buy_sell - 0.5) / 2.0, 0, 1)
                + 0.3 * clamp((unique_buyers / 200.0), 0, 1)
                + 0.3 * (1 - wash),
                0,
                1,
            ),
            buy_sell >= 1.0,
            f"B/S {buy_sell:.2f}",
            f"{int(buys)} buys / {int(sells)} sells in {window}; volume ${volume_usd:,.0f}; unique buyers estimated from tx count.",
            data={"buy_sell_ratio": round(buy_sell, 2), "unique_buyers": unique_buyers, "wash_pct": wash * 100, "window": window},
        )

        mom_score = clamp(0.6 * clamp((change5 + 30) / 120.0, 0, 1) + 0.4 * clamp((vol_liq - 0.1) / 2.5, 0, 1), 0, 1)
        checks["momentum"] = mk_check(
            "momentum",
            "Momentum",
            mom_score,
            change5 > 0 and vol_liq > 0.3,
            f"{change5:+.1f}% / 5m",
            f"Price {change5:+.1f}% recently; volume/liquidity {vol_liq:.2f}x.",
            data={"change_5m_pct": round(change5, 2), "volume_liquidity_ratio": round(vol_liq, 3)},
        )

        opp: dict[str, Any] = {
            "momentum": mk_metric("momentum", "Momentum", clamp((change5 + 30) / 120.0, 0, 1), f"{change5:+.1f}%", "Recent price change."),
            "volume": mk_metric("volume", "Volume acceleration", clamp((vol_liq - 0.1) / 2.8, 0, 1), f"{vol_liq:.2f}x", "Volume / liquidity."),
            "buyers": mk_metric("buyers", "Unique buyer growth", clamp(unique_buyers / 200.0, 0, 1), f"{unique_buyers}", "Buys in the short window (proxy)."),
            "buy_pressure": mk_metric("buy_pressure", "Buy pressure", clamp((buy_sell - 0.5) / 2.2, 0, 1), f"{buy_sell:.2f}", "Buy/sell transaction ratio."),
            "mcap_liquidity": mk_metric("mcap_liquidity", "Market cap vs liquidity", clamp(1 - (mcap_liq - 2) / 25, 0, 1), f"{mcap_liq:.1f}x", "Lower is healthier."),
            "wash": mk_metric("wash", "Wash-trading signal", wash, f"{wash * 100:.0f}%", "Wallet-level wash detection unavailable; conservative default.", {"available": False}),
        }

        hard = {
            "mint_authority_revoked": mint_revoked,
            "freeze_authority_revoked": freeze_revoked,
            "honeypot": honeypot["detected"],
            "top10_pct": top10_pct if holders_verified else 0.0,
            "top1_pct": top1_pct if holders_verified else 0.0,
            "liquidity_usd": liquidity,
            "price_usd": price,
            "holders": holder_count,
            "creator_rugs": int(creator["previous_rugs"]),
        }
        latent = {
            "quality": 0.0,
            "rug_probability": 0.25 if any("honeypot" in risk.lower() or "rug" in risk.lower() for risk in risks) else 0.12,
            "drift": 0.0,
            "volatility": 0.04,
        }
        return checks, opp, hard, latent

    async def _collect_live_data(
        self, mint: str, creator: str | None
    ) -> tuple[
        dict[str, Any] | None,
        dict[str, Any] | None,
        dict[str, Any] | None,
        dict[str, Any] | None,
        list[dict[str, Any]],
        bool | None,
    ]:
        import asyncio

        tasks = [
            self.clients.dexscreener_token(mint),
            self.clients.mint_info(mint),
            self.clients.rugcheck_summary(mint),
            self.clients.rugcheck_report(mint),
            self.clients.jupiter_sell_quote(mint),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        cleaned: list[Any] = [None if isinstance(r, Exception) else r for r in results]
        pair, mint_info, summary, report, sell_ok = cleaned
        assets: list[dict[str, Any]] = []
        if creator:
            try:
                assets = await self.clients.creator_assets(creator)
            except Exception:
                assets = []
        return pair, mint_info, summary, report, assets, sell_ok

    def _risk_names(self, summary: dict[str, Any] | None, report: dict[str, Any] | None) -> list[str]:
        risks = (summary or {}).get("risks") or (report or {}).get("risks") or []
        names: list[str] = []
        for risk in risks:
            if isinstance(risk, dict):
                name = str(risk.get("name") or risk.get("description") or "risk")
                names.append(name)
            elif risk:
                names.append(str(risk))
        return names

    def _lp_data(self, report: dict[str, Any] | None, risks: list[str]) -> dict[str, Any]:
        burned = False
        locked_days = 0
        detail = "LP status unavailable."
        markets = (report or {}).get("markets") or []
        for market in markets:
            lp = (market or {}).get("lp") or {}
            if lp.get("lpBurned"):
                burned = True
                detail = "LP tokens are burned."
                break
            locked_pct = safe_float(lp.get("lpLocked"))
            if locked_pct > 0:
                locked_days = 30
                detail = f"~{locked_pct:.0f}% of LP locked (duration unknown, assumed 30d)."
                break
        lowered = " ".join(risks).lower()
        if not burned and locked_days == 0 and ("lp" in lowered and ("unlock" in lowered or "not lock" in lowered or "no lp" in lowered)):
            detail = "LP appears unlocked — liquidity can be pulled."
        elif burned:
            pass
        elif locked_days == 0:
            detail = "No LP lock detected — treat as unlocked."
        return {"burned": burned, "locked_days": locked_days, "detail": detail, "verified": bool(markets)}

    def _holders_data(self, report: dict[str, Any] | None) -> dict[str, Any]:
        if not report:
            return {"top10_pct": 0.0, "top1_pct": 0.0, "count": 0, "growth_pct": 0.0, "verified": False}
        exclude = set()
        for market in report.get("markets") or []:
            if isinstance(market, dict):
                if market.get("pubkey"):
                    exclude.add(market["pubkey"])
                lp = market.get("lp") or {}
                for key in ("baseMint", "quoteMint"):
                    if lp.get(key):
                        exclude.add(lp[key])
        holders = [h for h in report.get("topHolders") or [] if isinstance(h, dict)]
        filtered = [h for h in holders if h.get("address") not in exclude]
        filtered.sort(key=lambda h: safe_float(h.get("pct")), reverse=True)
        top10 = sum(safe_float(h.get("pct")) for h in filtered[:10])
        top1 = safe_float(filtered[0].get("pct")) if filtered else 0.0
        count = int(safe_float(report.get("totalHolders"), len(filtered)))
        return {
            "top10_pct": round(top10, 2),
            "top1_pct": round(top1, 2),
            "count": count,
            "growth_pct": 0.0,
            "verified": bool(filtered) or count > 0,
            "holders": [
                {"address": h.get("address"), "pct": safe_float(h.get("pct")), "insider": bool(h.get("insider"))}
                for h in filtered[:10]
            ],
        }

    def _creator_data(
        self,
        report: dict[str, Any] | None,
        risks: list[str],
        assets: list[dict[str, Any]],
        creator: str | None,
    ) -> dict[str, Any]:
        rugs = 0
        for risk in risks:
            lowered = risk.lower()
            if "creator" in lowered and ("rug" in lowered or "history" in lowered or "sell" in lowered):
                rugs += 1
        wallet = (report or {}).get("creator") or creator or "unknown"
        holds = 0.0
        for holder in (report or {}).get("topHolders") or []:
            if isinstance(holder, dict) and holder.get("address") == wallet:
                holds = safe_float(holder.get("pct"))
                break
        return {
            "wallet": wallet,
            "tokens_launched": len(assets),
            "previous_rugs": rugs,
            "holds_pct": round(holds, 2),
            "estimated": True,
        }

    def _bundle_data(
        self, summary: dict[str, Any] | None, report: dict[str, Any] | None, risks: list[str], top10_pct: float
    ) -> dict[str, Any]:
        available = bool(summary or report)
        flagged = [risk for risk in risks if any(word in risk.lower() for word in ("bundle", "sniper", "insider", "linked"))]
        cluster = min(60.0, top10_pct * 0.55) if flagged else (min(8.0, top10_pct * 0.15) if available else 0.0)
        return {
            "available": available,
            "cluster_pct": round(cluster, 2),
            "sniper_wallets": len(flagged) * 2,
            "signals": flagged,
        }

    def _honeypot_data(self, sell_ok: bool | None, risks: list[str]) -> dict[str, Any]:
        risk_honeypot = any("honeypot" in risk.lower() for risk in risks)
        if sell_ok is True:
            detected: bool | None = False
            detail = "Jupiter sell quote succeeded; token is sellable."
        elif sell_ok is False:
            detected = True
            detail = "Sell quote failed; likely honeypot or zero liquidity."
        elif risk_honeypot:
            detected = True
            detail = "RugCheck reports honeypot risk."
        else:
            detected = None
            detail = "Sell simulation unavailable (Jupiter/RugCheck) — unverified."
        return {"detected": detected, "can_sell": sell_ok, "detail": detail}

    def _fallback_analysis(self, token: NewToken, error: str) -> Analysis:
        checks = {
            "mint_authority": mk_check("mint_authority", "Mint authority revoked", 0.0, False, "UNVERIFIED", "Analysis failed.", critical=True, data={"authority": None}),
            "freeze_authority": mk_check("freeze_authority", "Freeze authority revoked", 0.0, False, "UNVERIFIED", "Analysis failed.", critical=True, data={"authority": None}),
            "liquidity": mk_check("liquidity", "Liquidity depth", 0.0, False, "Unknown", "Analysis failed.", data={"usd": 0}),
            "honeypot": mk_check("honeypot", "Honeypot / sell-ability", 0.0, False, "UNVERIFIED", "Analysis failed.", critical=True, data={"detected": None}),
        }
        hard = {
            "mint_authority_revoked": None,
            "freeze_authority_revoked": None,
            "honeypot": None,
            "top10_pct": 0.0,
            "liquidity_usd": 0.0,
            "price_usd": token.price_usd,
            "holders": 0,
            "creator_rugs": 0,
        }
        scores = score_token(checks, {}, self.get_config().strategy, hard)
        return Analysis(
            checks=checks,
            opportunity_metrics={},
            hard_data=hard,
            scores=scores,
            archetype=token.archetype or "unknown",
            flags={"error": error},
        )

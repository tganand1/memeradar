type SoundKind = "buy" | "sell" | "win" | "error" | "alert";

let context: AudioContext | null = null;

function getContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  if (!context) {
    const Ctor = window.AudioContext || (window as any).webkitAudioContext;
    if (!Ctor) return null;
    context = new Ctor();
  }
  return context;
}

function tone(ctx: AudioContext, frequency: number, start: number, length: number, gainValue: number, type: OscillatorType) {
  const oscillator = ctx.createOscillator();
  const gain = ctx.createGain();
  oscillator.type = type;
  oscillator.frequency.setValueAtTime(frequency, start);
  gain.gain.setValueAtTime(0.0001, start);
  gain.gain.exponentialRampToValueAtTime(gainValue, start + 0.015);
  gain.gain.exponentialRampToValueAtTime(0.0001, start + length);
  oscillator.connect(gain);
  gain.connect(ctx.destination);
  oscillator.start(start);
  oscillator.stop(start + length + 0.02);
}

export function playSound(kind: SoundKind) {
  const ctx = getContext();
  if (!ctx) return;
  if (ctx.state === "suspended") {
    void ctx.resume();
  }
  const now = ctx.currentTime;
  if (kind === "buy") {
    tone(ctx, 660, now, 0.14, 0.045, "sine");
    tone(ctx, 990, now + 0.09, 0.18, 0.04, "sine");
  } else if (kind === "sell") {
    tone(ctx, 520, now, 0.13, 0.04, "sine");
    tone(ctx, 390, now + 0.08, 0.18, 0.035, "sine");
  } else if (kind === "win") {
    [523, 659, 784, 1047].forEach((freq, index) => tone(ctx, freq, now + index * 0.07, 0.18, 0.04, "triangle"));
  } else if (kind === "error") {
    tone(ctx, 210, now, 0.22, 0.05, "sawtooth");
    tone(ctx, 160, now + 0.12, 0.28, 0.04, "sawtooth");
  } else {
    tone(ctx, 880, now, 0.1, 0.035, "square");
    tone(ctx, 880, now + 0.16, 0.1, 0.03, "square");
  }
}

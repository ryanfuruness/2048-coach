/** Token buckets per key (client IP and endpoint class): `rate` tokens per `per` ms, at most `burst` saved up. */
export class RateLimiter {
  private buckets = new Map<string, { tokens: number; at: number }>();
  private lastSweep = 0;
  private rate: number;
  private per: number;
  private burst: number;
  private now: () => number;
  constructor(rate: number, per: number, burst: number, now: () => number = Date.now) {
    this.rate = rate;
    this.per = per;
    this.burst = burst;
    this.now = now;
  }

  /** Takes one token; returns 0 if allowed, else the milliseconds until a token is available. */
  take(key: string): number {
    const t = this.now();
    this.sweep(t);
    let b = this.buckets.get(key);
    if (!b) {
      b = { tokens: this.burst, at: t };
      this.buckets.set(key, b);
    }
    b.tokens = Math.min(this.burst, b.tokens + ((t - b.at) * this.rate) / this.per);
    b.at = t;
    if (b.tokens >= 1) {
      b.tokens -= 1;
      return 0;
    }
    return Math.ceil(((1 - b.tokens) * this.per) / this.rate);
  }

  // forget full buckets now and then, so the map does not grow with every client ever seen
  private sweep(t: number): void {
    if (t - this.lastSweep < 60000) return;
    this.lastSweep = t;
    for (const [k, b] of this.buckets)
      if (b.tokens + ((t - b.at) * this.rate) / this.per >= this.burst) this.buckets.delete(k);
  }

  get size(): number {
    return this.buckets.size;
  }
}

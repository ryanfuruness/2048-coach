/** A small least-recently-used cache (Map keeps insertion order). */
export class Lru<V> {
  private map = new Map<string, V>();
  private max: number;
  constructor(max: number) {
    this.max = max;
  }
  get(key: string): V | undefined {
    const v = this.map.get(key);
    if (v === undefined) return undefined;
    this.map.delete(key);
    this.map.set(key, v);
    return v;
  }
  set(key: string, value: V): void {
    if (this.max <= 0) return;
    this.map.delete(key);
    this.map.set(key, value);
    while (this.map.size > this.max) this.map.delete(this.map.keys().next().value as string);
  }
  get size(): number {
    return this.map.size;
  }
}

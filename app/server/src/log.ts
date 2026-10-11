/** One JSON object per line on stdout: easy to read locally, easy to ship to a log service later. */
export function log(event: string, fields: Record<string, unknown> = {}): void {
  process.stdout.write(JSON.stringify({ t: new Date().toISOString(), event, ...fields }) + '\n');
}

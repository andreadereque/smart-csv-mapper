/** "1 row", "2 rows". */
export function rows(count: number): string {
  if (count === 1) {
    return "1 row";
  }
  return `${count} rows`;
}

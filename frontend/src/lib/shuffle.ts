/**
 * Module: src/lib/shuffle.ts
 * Layer: Lib
 * Purpose: A random order for a list of cards, different on every render.
 *
 *          Used by the pages that show people as a cohort rather than a
 *          catalogue — /fellows, /alumni, /challengers and the belts on the fellow
 *          program page — so nobody is permanently stuck at the end of an alphabet.
 *          It happens in the page, not the API: the API's payload stays identical
 *          across requests, so its ETag still earns a 304 and it stays cacheable.
 *          A page that shuffles must also say `Cache-Control: no-store`, or a
 *          browser would reuse one shuffle for the next 30 seconds of reloads.
 *
 * Called by: src/pages/{fellows,alumni,challengers,fellow-program}.astro,
 *            src/components/PeopleDirectory.astro
 * Calls: nothing
 */

/**
 * A shuffled copy, Fisher-Yates. The input is left as it was.
 *
 * Display order only, never a secret — `Math.random` is the right tool.
 *
 * @param list Anything to put in a random order.
 * @returns A new array with the same items.
 */
export function shuffled<T>(list: readonly T[]): T[] {
  const out = [...list];
  for (let i = out.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

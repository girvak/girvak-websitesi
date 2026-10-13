// ============================================================
// GİRVAK — the rules of the /apply cards, as pure functions.
//
// Run on the server for every request, so a deadline passes at midnight in
// İstanbul for every visitor at once, whatever their own clock or time zone
// says, and whatever the API's snapshot was built from. Tested by
// tests/open-calls.test.js.
// ============================================================

/** A call with this many days or fewer left is shown as closing soon. */
export const URGENT_DAYS = 7;

const TIME_ZONE = 'Europe/Istanbul';
const DAY_MS = 86_400_000;

/**
 * Today's date in İstanbul, as `YYYY-MM-DD`.
 * @param {Date} [now]
 * @returns {string}
 */
export function todayIn(now = new Date()) {
  // en-CA formats a date as YYYY-MM-DD.
  return new Intl.DateTimeFormat('en-CA', { timeZone: TIME_ZONE }).format(now);
}

/**
 * Whole days from `today` to `deadline`; negative once it has passed.
 * @param {string} deadline `YYYY-MM-DD`
 * @param {string} today `YYYY-MM-DD`
 * @returns {number}
 */
export function daysLeft(deadline, today) {
  return Math.round((Date.parse(`${deadline}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / DAY_MS);
}

/**
 * @typedef {{ title: string, text: string, href: string, deadline: string | null, popup: boolean }} OpenCall
 * @typedef {'always' | 'open' | 'urgent' | 'closed'} CallState
 * @typedef {OpenCall & { state: CallState, days: number }} RatedCall
 */

/**
 * State of one call on `today`. The deadline day itself is still open.
 * @param {OpenCall} call
 * @param {string} today
 * @returns {RatedCall}
 */
export function rate(call, today) {
  if (!call.deadline) return { ...call, state: 'always', days: Infinity };
  const days = daysLeft(call.deadline, today);
  const state = days < 0 ? 'closed' : days <= URGENT_DAYS ? 'urgent' : 'open';
  return { ...call, state, days };
}

/**
 * The page's order: always-open calls first, then open ones by the nearest
 * deadline, then closed ones, most recently closed first. Ties keep the
 * Airtable order.
 * @param {OpenCall[]} calls
 * @param {string} today
 * @returns {RatedCall[]}
 */
export function arrange(calls, today) {
  const rank = (/** @type {RatedCall} */ c) => (c.state === 'always' ? 0 : c.state === 'closed' ? 2 : 1);
  return calls
    .map((call) => rate(call, today))
    .sort((a, b) => {
      if (rank(a) !== rank(b)) return rank(a) - rank(b);
      if (a.state === 'always') return 0;
      return a.state === 'closed' ? b.days - a.days : a.days - b.days;
    });
}

/**
 * The calls the home page popup shows: ticked `popup` and not closed, in the
 * page's order. A call whose deadline passes drops out the next day by itself.
 * @param {OpenCall[]} calls
 * @param {string} today
 * @returns {RatedCall[]}
 */
export function popupCalls(calls, today) {
  return arrange(calls, today).filter((c) => c.popup && c.state !== 'closed');
}

/**
 * The deadline as the card prints it: `5 September`, with the year added only
 * when it is not this year's.
 * @param {string} deadline `YYYY-MM-DD`
 * @param {string} today `YYYY-MM-DD`
 * @returns {string}
 */
export function formatDeadline(deadline, today) {
  const sameYear = deadline.slice(0, 4) === today.slice(0, 4);
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'long',
    ...(sameYear ? {} : { year: 'numeric' }),
    timeZone: 'UTC',
  }).format(new Date(`${deadline}T00:00:00Z`));
}

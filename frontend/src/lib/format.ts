/**
 * Formats every date, time and number shown on screen.
 *
 * Doing it all in one place means they're always shown the same way, in the
 * style of the reader's country. The formatters are set up once when the file
 * loads, because setting one up is the slow part.
 */

const DATE = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "numeric",
});

const DATE_TIME = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

const INTEGER = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });

const PERCENT_1DP = new Intl.NumberFormat(undefined, {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

/**
 * A date with no time, like "2021-11-29".
 *
 * It deliberately doesn't use `new Date(value)`. That reads the date as
 * midnight in London, so anywhere west of London it would show the day
 * *before*. Splitting the text apart keeps the day shown the same as the day
 * saved.
 */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return value;
  return DATE.format(new Date(year, month - 1, day));
}

/** A date and time, like "2026-10-02T09:15:00Z", shown in the reader's own
 *  time zone. */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : DATE_TIME.format(parsed);
}

export function formatCount(value: number): string {
  return INTEGER.format(value);
}

/** Turns 0.0731 into 7.3%. Give it a fraction, not a number already
 *  multiplied by 100. */
export function formatRate(value: number): string {
  return PERCENT_1DP.format(value);
}

/** A difference between two percentages, like "+12.3 pp". */
export function formatPercentagePoints(value: number): string {
  // A non-breaking space before "pp", so it never splits across two lines.
  return `+${(value * 100).toFixed(1)} pp`;
}

/**
 * Writes "1 filter" or "2 filters" properly, instead of "filter(s)".
 */
export function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return `${formatCount(count)} ${count === 1 ? singular : plural}`;
}

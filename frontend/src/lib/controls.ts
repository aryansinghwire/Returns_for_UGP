/**
 * Shared styles for form fields and buttons, so they look the same everywhere.
 *
 * Everything here is black, white or grey. Colour on this site means one
 * thing only - how risky an order is - so nothing else uses colour to compete
 * with it. lib/risk.ts is the only place colour is allowed.
 *
 * Rounded corners say what something is: form fields are barely rounded
 * (2px), boxes that float above the page are a little more (4px), and table
 * rows aren't rounded at all.
 */

export const LABEL = "block font-condensed text-meta font-medium text-ink-muted";

export const HINT = "mt-1 text-meta text-ink-muted";

/** Text boxes, dropdowns and text areas. The text colour is set on purpose:
 *  without it, Windows dark mode can show dark text on a dark background. */
/* A darker border than the dividers use. A field's edge is how you see where
   the field is, so it needs to stand out clearly - the lighter divider grey
   would make the field almost invisible. */
export const CONTROL =
  "rounded-[2px] border border-rule-strong bg-paper px-2 py-1 text-body text-ink " +
  "hover:border-ink disabled:cursor-not-allowed disabled:opacity-50";

/** CONTROL, plus the gap needed when the field sits under its label. */
export const CONTROL_STACKED = `mt-1 ${CONTROL}`;

/** The main button - dark, to stand out. Used once per page at most. */
export const BUTTON_PRIMARY =
  "rounded-[2px] bg-ink px-3 py-1.5 text-body font-medium text-paper " +
  "hover:opacity-85 active:opacity-75 disabled:cursor-not-allowed " +
  "disabled:opacity-40 disabled:hover:opacity-40";

export const BUTTON_SECONDARY =
  "rounded-[2px] border border-rule-strong px-3 py-1.5 text-body font-medium text-ink " +
  "hover:bg-panel active:border-ink-muted disabled:cursor-not-allowed " +
  "disabled:opacity-40 disabled:hover:bg-transparent";

/** A smaller button, for use inside tables and lists. */
export const BUTTON_SMALL =
  "rounded-[2px] border border-rule-strong px-2 py-0.5 text-meta font-medium text-ink " +
  "hover:bg-panel disabled:cursor-not-allowed disabled:opacity-40 " +
  "disabled:hover:bg-transparent";

/**
 * Links are underlined rather than coloured - colour is kept for risk, and
 * underlines are easier to read anyway.
 */
export const LINK = "underline decoration-rule underline-offset-2 hover:decoration-ink";

/** Table column headings: normal capitalisation in a narrower font, not
 *  spaced-out capital letters. */
export const TH = "font-condensed text-meta font-semibold text-ink-muted";

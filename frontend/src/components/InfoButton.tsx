import { useEffect, useId, useRef, useState, type ReactNode } from "react";

/**
 * A small "i" button that opens a note explaining the thing next to it.
 *
 * The dashboard used to have two paragraphs of background and warnings under
 * the numbers, drawing attention away from the numbers people came for. The
 * notes still matter - without them it's easy to misread a date range over
 * made-up dates, or a count of actions nobody will ever report back on - so
 * they moved behind this button instead of being deleted.
 *
 * It's a button that opens a panel, not a tooltip. Tooltips only appear when
 * you hover with a mouse, so they don't work on touch screens or with a
 * keyboard. This is a real button that tells screen readers whether it's
 * open. It closes on Escape or a click elsewhere, and on Escape it puts
 * keyboard focus back on itself.
 *
 * The circle is the one place that breaks the corner-rounding rules in
 * lib/controls.ts (2px on controls, 4px on floating panels, none on table
 * rows). A round "i" is so widely recognised that it's worth the exception.
 * The panel it opens is a floating panel, so it keeps the usual 4px.
 */
export default function InfoButton({
  label,
  children,
}: {
  /** What screen readers call the button, e.g. "About the period". */
  label: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const wrap = useRef<HTMLSpanElement>(null);
  const button = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setOpen(false);
      // If focus isn't put somewhere after Escape, a keyboard user is left stuck.
      button.current?.focus();
    }
    function onPointerDown(event: PointerEvent) {
      if (!wrap.current?.contains(event.target as Node)) setOpen(false);
    }

    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("pointerdown", onPointerDown);
    };
  }, [open]);

  return (
    <span ref={wrap} className="relative inline-flex">
      <button
        ref={button}
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((current) => !current)}
        className={
          "flex h-5 w-5 items-center justify-center rounded-full border border-rule-strong " +
          "font-condensed text-body font-semibold leading-none text-ink-muted " +
          "hover:border-ink hover:text-ink aria-expanded:border-ink aria-expanded:bg-ink " +
          "aria-expanded:text-paper"
        }
      >
        i
      </button>
      {open && (
        <span
          id={panelId}
          role="note"
          className={
            "absolute left-0 top-7 z-10 block w-[min(44ch,70vw)] rounded-[4px] border " +
            "border-rule-strong bg-paper p-3 text-head text-ink-muted shadow-lg"
          }
        >
          {children}
        </span>
      )}
    </span>
  );
}

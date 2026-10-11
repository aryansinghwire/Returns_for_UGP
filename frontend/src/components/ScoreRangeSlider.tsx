import { useEffect, useId, useRef, useState } from "react";

const ADJUSTMENT_KEYS = new Set(["Home", "End", "PageUp", "PageDown"]);

/**
 * A slider with two handles, for picking a range of risk scores.
 *
 * It's two of the browser's own sliders stacked on top of each other, rather
 * than a library: that keeps full keyboard support and adds nothing to
 * install. Their tracks are invisible and ignore the mouse, so only the
 * handles can be grabbed and the two sliders don't fight over a drag. The
 * track you see, and the highlighted range, are drawn underneath.
 *
 * `onChange` fires over and over while a handle moves; `onCommit` fires once,
 * when the user lets go. Anything that saves to the server should use
 * `onCommit` - otherwise one drag sends a request for every pixel moved.
 */
export default function ScoreRangeSlider({
  min,
  max,
  onChange,
  onCommit,
  disabled = false,
  label = "Score window",
  className = "w-64",
}: {
  min: number;
  max: number;
  onChange: (next: { min: number; max: number }) => void;
  /** Called when the user lets go of a handle, or finishes with the keyboard. */
  onCommit?: () => void;
  disabled?: boolean;
  label?: string;
  /** Width and spacing, set by whoever uses the slider. */
  className?: string;
}) {
  const id = useId();
  const [dragging, setDragging] = useState(false);
  const pct = (v: number) => `${Math.round(v * 100)}%`;

  // Kept in a ref so the listener below is added once per drag, not again on
  // every re-render the drag causes. It's updated in an effect rather than
  // during render, because React sometimes throws a render away, and that
  // mustn't leave a change behind.
  const onCommitRef = useRef(onCommit);
  useEffect(() => {
    onCommitRef.current = onCommit;
  });

  /**
   * Listen for the mouse being let go on the whole window, not just here.
   *
   * People often press on a handle and let go somewhere else entirely - it's a
   * drag, and the handle is only 17px wide. When this only listened on the
   * slider, a release outside it was missed: the change was never saved, and
   * text on the page stayed unselectable.
   */
  useEffect(() => {
    if (!dragging) return;

    function end() {
      setDragging(false);
      onCommitRef.current?.();
    }

    window.addEventListener("pointerup", end);
    window.addEventListener("pointercancel", end);
    return () => {
      window.removeEventListener("pointerup", end);
      window.removeEventListener("pointercancel", end);
    };
  }, [dragging]);

  /** The arrow, Home, End, Page Up and Page Down keys move a handle without any mouse event, so save the change here. */
  function onKeyUp(e: React.KeyboardEvent) {
    if (e.key.startsWith("Arrow") || ADJUSTMENT_KEYS.has(e.key)) onCommitRef.current?.();
  }

  return (
    <div className={`${className} ${dragging ? "range-dragging" : ""}`}>
      <div className="flex items-baseline justify-between gap-2">
        {/* A label for the pair, not a <label for>: there are two sliders and
            this text belongs to neither one. Each slider already has its own
            aria-label below, which would override a <label for> - so this
            visible text would never be read out to anyone. */}
        <span id={`${id}-label`} className="font-condensed text-meta font-medium text-ink-muted">
          {label}
        </span>
        <output
          htmlFor={`${id}-min ${id}-max`}
          className="font-mono text-meta tabular-nums text-ink"
        >
          {min.toFixed(2)} – {max.toFixed(2)}
        </output>
      </div>

      <div
        role="group"
        aria-labelledby={`${id}-label`}
        /* Moving focus away from both sliders saves the last change. */
        onBlur={() => onCommitRef.current?.()}
        className={`relative mt-3 h-5 ${disabled ? "opacity-40" : ""}`}
      >
        {/* the whole track */}
        <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-rule" />
        {/* the chosen range */}
        <div
          className="absolute top-1/2 h-px -translate-y-1/2 bg-ink"
          style={{ left: pct(min), right: `${Math.round((1 - max) * 100)}%` }}
        />
        <input
          id={`${id}-min`}
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={min}
          disabled={disabled}
          aria-label={`${label}, lower bound`}
          aria-valuetext={`${min.toFixed(2)}, upper bound ${max.toFixed(2)}`}
          onPointerDown={() => setDragging(true)}
          onKeyUp={onKeyUp}
          onChange={(e) => onChange({ min: Math.min(Number(e.target.value), max), max })}
          className="range-thumb absolute inset-x-0 top-0 h-5 w-full"
        />
        <input
          id={`${id}-max`}
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={max}
          disabled={disabled}
          aria-label={`${label}, upper bound`}
          aria-valuetext={`${max.toFixed(2)}, lower bound ${min.toFixed(2)}`}
          onPointerDown={() => setDragging(true)}
          onKeyUp={onKeyUp}
          onChange={(e) => onChange({ min, max: Math.max(Number(e.target.value), min) })}
          className="range-thumb absolute inset-x-0 top-0 h-5 w-full"
        />
      </div>

      <div className="mt-1 flex justify-between font-condensed text-meta text-ink-muted">
        <span>0.00 lower risk</span>
        <span>higher risk 1.00</span>
      </div>
    </div>
  );
}

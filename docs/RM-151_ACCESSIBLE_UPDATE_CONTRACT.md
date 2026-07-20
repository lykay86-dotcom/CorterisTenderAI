# RM-151 accessible operation update contract

## Scope boundary

RM-151 supplies stable semantic text, actions and deterministic announcement coalescing. Full
Tab/Shift+Tab, Narrator, high-contrast and physical DPI certification remains RM-152.

## Presentation requirements

- Operation controls have explicit accessible name, action text and subject where safe.
- State is visible as text/semantics, never only colour, icon, animation or disabled styling.
- Safe title/summary and correlation ID are available in markup-free accessible text.
- Retry/cancel/open-result/open-diagnostics controls are native keyboard-focusable controls when
  capability exists; disabled controls expose a safe reason.
- Progress updates never steal focus. Closing/dismissing feedback restores the existing focus
  origin through RM-142/RM-143 behavior.
- Notification rows expose stable identity, time, severity, read state, title, summary and action
  in deterministic reading order. Dynamic rich markup is absent from accessible text.

## Deterministic coalescing

The coalescer uses injected logical time and semantic progress buckets, not `sleep` or wall-clock
races. Start, phase change and terminal events are always independently eligible. Identical
generation/revision/fingerprint updates are suppressed. Terminal events are never suppressed.

Initial measured policy candidate:

- bounded progress announces at start, each new 10-percent bucket and terminal;
- indeterminate progress announces start and allowlisted phase changes only;
- provider-level events with unchanged aggregate phase/bucket are coalesced;
- severity escalation and new actionable partial failure announce immediately;
- one terminal episode produces one announcement even when in-surface, status bar and notification
  projections all update.

The 10-percent value is provisional until the characterization benchmark records announcement
counts for 0/1/100/1,000/10,000 events. Correctness bounds, not elapsed time, determine acceptance.

## Boundedness

Coalescer state is bounded per active episode and removed after terminal/close. It stores only last
generation/revision, phase, bucket and terminal fingerprint. One thousand identical duplicates
produce at most one non-terminal announcement; 10,000 monotonically increasing bounded events
produce at most 12 announcements for one phase (start, buckets, terminal), subject to measured
final policy.

## Modal and notification behavior

Generic progress does not open modal dialogs. Blocking confirmation remains explicit, has safe
default/cancel behavior and names exact target. Terminal persistent notification is used only by
routing policy. Badge changes alone are not the terminal announcement.

## Tests and residuals

Expected-red tests use a logical clock and verify duplicate suppression, phase/bucket changes,
terminal non-suppression, focus invariance, markup-free accessible text, keyboard action metadata
and deterministic reading order. Manual Narrator, physical keyboard, contrast and DPI are recorded
as `NOT_EXECUTED` unless actually performed and passed to RM-152.


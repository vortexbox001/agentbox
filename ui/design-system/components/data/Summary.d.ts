/**
 * Summary — the visual treatment for the FR-007 markdown subset produced by render_summary.
 * @startingPoint section="Components" subtitle="Rendered final message" viewport="700x200"
 */
export interface SummaryProps {
  html?: string;                 // pre-rendered, escaped subset HTML
  fallback?: React.ReactNode;    // foot-line fallback when no message exists
}
export function Summary(props: SummaryProps): JSX.Element;

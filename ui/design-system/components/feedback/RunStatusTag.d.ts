/**
 * RunStatusTag — run status pill: colored dot + label. Neutral gray for started/running.
 * @startingPoint section="Components" subtitle="Run status pill" viewport="700x80"
 */
export interface RunStatusTagProps {
  status?: 'success' | 'failure' | 'error' | 'started' | 'running' | 'queued' | 'canceled';
  /** Text shown; defaults to the status name. Pass a relative time like "2 hours ago". */
  label?: string;
  style?: React.CSSProperties;
}
export function RunStatusTag(props: RunStatusTagProps): JSX.Element;

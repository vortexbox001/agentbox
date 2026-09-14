/**
 * Badge — small status indicator label.
 * Use for run/agent status, tags, and category labels.
 *
 * @startingPoint section="Components" subtitle="Status badges for runs and agents" viewport="700x80"
 */
export interface BadgeProps {
  label: string;
  intent?: 'running' | 'success' | 'error' | 'warning' | 'queued' | 'scheduled' | 'default' | 'primary' | 'lime';
  style?: React.CSSProperties;
}
export function Badge(props: BadgeProps): JSX.Element;

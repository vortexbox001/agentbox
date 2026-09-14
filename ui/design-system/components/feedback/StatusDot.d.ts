/**
 * StatusDot — colored circle indicating status.
 * @startingPoint section="Components" subtitle="Status indicator dots" viewport="700x60"
 */
export interface StatusDotProps {
  status?: 'running' | 'success' | 'error' | 'warning' | 'scheduled' | 'idle';
  size?: number;
  style?: React.CSSProperties;
}
export function StatusDot(props: StatusDotProps): JSX.Element;

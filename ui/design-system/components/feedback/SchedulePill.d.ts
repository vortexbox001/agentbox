/**
 * SchedulePill — schedule/sensor chip: icon + human-readable frequency + inline on/off toggle.
 * @startingPoint section="Components" subtitle="Schedule / sensor chip with toggle" viewport="700x80"
 */
export interface SchedulePillProps {
  type?: 'schedule' | 'sensor';
  /** Human-readable frequency, e.g. "Every day at 7:00 AM". */
  label: string;
  on?: boolean;
  onToggle?: () => void;
  style?: React.CSSProperties;
}
export function SchedulePill(props: SchedulePillProps): JSX.Element;

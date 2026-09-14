/**
 * Button — primary interactive control.
 * Use for actions, submissions, and navigation triggers.
 *
 * @startingPoint section="Components" subtitle="Primary, outlined, and intent buttons" viewport="700x200"
 */
export interface ButtonProps {
  /** Button label text */
  children?: React.ReactNode;
  /** Visual intent: primary, danger, success, warning */
  intent?: 'primary' | 'danger' | 'success' | 'warning';
  /** Outlined style (border only, no fill) */
  outlined?: boolean;
  /** Disabled state */
  disabled?: boolean;
  /** Loading state — shows spinner */
  loading?: boolean;
  /** Leading icon element */
  icon?: React.ReactNode;
  /** Trailing icon element */
  rightIcon?: React.ReactNode;
  /** Click handler */
  onClick?: () => void;
  /** Inline style overrides */
  style?: React.CSSProperties;
  /** Additional CSS class */
  className?: string;
}
export function Button(props: ButtonProps): JSX.Element;

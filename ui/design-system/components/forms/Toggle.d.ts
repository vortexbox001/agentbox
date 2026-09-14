/**
 * Toggle — on/off switch control.
 * @startingPoint section="Components" subtitle="Toggle switch with teal active" viewport="700x60"
 */
export interface ToggleProps {
  checked?: boolean;
  onChange?: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
  style?: React.CSSProperties;
}
export function Toggle(props: ToggleProps): JSX.Element;

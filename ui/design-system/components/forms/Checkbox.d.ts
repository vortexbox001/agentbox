/**
 * Checkbox — toggle control with label.
 * @startingPoint section="Components" subtitle="Checkbox with teal checked state" viewport="700x60"
 */
export interface CheckboxProps {
  checked?: boolean;
  onChange?: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
  style?: React.CSSProperties;
}
export function Checkbox(props: CheckboxProps): JSX.Element;

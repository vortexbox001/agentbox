/**
 * Select — native dropdown with custom chevron styling.
 * @startingPoint section="Components" subtitle="Select dropdown" viewport="700x100"
 */
export interface SelectProps {
  label?: string;
  value?: string;
  onChange?: (value: string) => void;
  options?: (string | { value: string; label: string })[];
  disabled?: boolean;
  style?: React.CSSProperties;
}
export function Select(props: SelectProps): JSX.Element;

/**
 * TextInput — text field with optional label and error state.
 * @startingPoint section="Components" subtitle="Text input with label" viewport="700x100"
 */
export interface TextInputProps {
  label?: string;
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  error?: string | boolean;
  type?: string;
  style?: React.CSSProperties;
  inputStyle?: React.CSSProperties;
}
export function TextInput(props: TextInputProps): JSX.Element;

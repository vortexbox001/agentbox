/**
 * Dialog — modal overlay with backdrop blur.
 * @startingPoint section="Components" subtitle="Modal dialog" viewport="700x400"
 */
export interface DialogProps {
  open: boolean;
  onClose?: () => void;
  title?: string;
  subtitle?: string;
  children?: React.ReactNode;
  width?: number;
  style?: React.CSSProperties;
}
export function Dialog(props: DialogProps): JSX.Element;

/**
 * Alert — info/warning/error/success banner.
 * @startingPoint section="Components" subtitle="Alert banners" viewport="700x100"
 */
export interface AlertProps {
  intent?: 'info' | 'warning' | 'error' | 'success';
  title?: string;
  children?: React.ReactNode;
  style?: React.CSSProperties;
}
export function Alert(props: AlertProps): JSX.Element;

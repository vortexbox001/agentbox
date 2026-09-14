/**
 * Card — content container with border, no shadow.
 * @startingPoint section="Components" subtitle="Content container card" viewport="700x120"
 */
export interface CardProps {
  children: React.ReactNode;
  interactive?: boolean;
  style?: React.CSSProperties;
  onClick?: () => void;
}
export function Card(props: CardProps): JSX.Element;

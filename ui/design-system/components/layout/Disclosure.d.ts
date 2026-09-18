/**
 * Disclosure — a bordered section card with a keyboard-operable collapsible header.
 * @startingPoint section="Components" subtitle="Collapsible section card" viewport="700x160"
 */
export interface DisclosureProps {
  title: string;
  note?: string;
  open?: boolean;
  id: string;
  children: React.ReactNode;
}
export function Disclosure(props: DisclosureProps): JSX.Element;

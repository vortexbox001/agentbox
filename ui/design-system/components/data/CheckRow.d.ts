/**
 * CheckRow — one recorded check, reusing the ax-result mark of the Agents overview.
 * @startingPoint section="Components" subtitle="Check result row" viewport="700x100"
 */
export interface CheckRowProps {
  status: 'pass' | 'warn' | 'fail-blocking' | 'not-run';
  name: string;
  detail?: string;
  recorded?: string;
}
export function CheckRow(props: CheckRowProps): JSX.Element;

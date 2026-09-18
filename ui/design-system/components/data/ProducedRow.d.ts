/**
 * ProducedRow — a best-effort "produced elsewhere" row (pull request / commit / file).
 * @startingPoint section="Components" subtitle="Produced-elsewhere row" viewport="700x100"
 */
export interface ProducedRowProps {
  kind: 'pull_request' | 'commit' | 'file';
  identifier: string;
  action?: string;   // Open (URL) / Preview (file) / none
}
export function ProducedRow(props: ProducedRowProps): JSX.Element;

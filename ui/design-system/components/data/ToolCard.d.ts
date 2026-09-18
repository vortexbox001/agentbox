/**
 * ToolCard — a compact IN/OUT transcript tool card, clamped to 3 lines with expand-on-click.
 * @startingPoint section="Components" subtitle="IN/OUT tool card" viewport="700x260"
 */
export interface ToolCardProps {
  name: string;
  description?: string;
  marker?: string;            // "exit N" | "failed" | none
  in_text?: string;
  out_text?: string;
  in_overflow?: boolean;
  out_overflow?: boolean;
  in_lines?: number;
  out_lines?: number;
  is_diff?: boolean;
  out_intent?: 'failed' | 'missing';
}
export function ToolCard(props: ToolCardProps): JSX.Element;

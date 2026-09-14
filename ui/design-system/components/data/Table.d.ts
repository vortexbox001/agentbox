/**
 * Table — grid-based data table with header and rows.
 * @startingPoint section="Components" subtitle="Data table with optional gridlines" viewport="700x250"
 */
export interface TableColumn {
  key?: string;
  label: string;
  width?: string;
  render?: (row: any, index: number) => React.ReactNode;
}
export interface TableProps {
  columns: TableColumn[];
  rows: any[];
  onRowClick?: (row: any, index: number) => void;
  /** Object-overview layout (Dagster Runs pattern): horizontal rules edge to edge, a 2px header rule, per-column vertical dividers, first/last cells inset 24px. Default false = detail-page layout (inset content, hairline rules, no vertical dividers). */
  fullBleed?: boolean;
  style?: React.CSSProperties;
}
export function Table(props: TableProps): JSX.Element;

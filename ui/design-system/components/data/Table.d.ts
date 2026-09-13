/**
 * Table — grid-based data table with header and rows.
 * @startingPoint section="Components" subtitle="Data table with column config" viewport="700x250"
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
  style?: React.CSSProperties;
}
export function Table(props: TableProps): JSX.Element;

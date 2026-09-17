/**
 * Pagination — Prev · page indicator · Next, for paging a list view.
 * Prev is disabled on the first page, Next on the last; page state lives in the URL
 * (the served macro renders real ?page= links so it works without JS).
 * @startingPoint section="Components" subtitle="Prev · indicator · Next" viewport="700x80"
 */
export interface PaginationProps {
  /** current 1-based page */
  page?: number;
  /** total page count (≥ 1) */
  pages?: number;
  /** called with the next page number when Prev/Next is activated */
  onChange?: (page: number) => void;
  style?: React.CSSProperties;
}
export function Pagination(props: PaginationProps): JSX.Element;

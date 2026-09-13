/**
 * Tabs + Tab — horizontal tab navigation with bottom-border indicator.
 * Matches Dagster's tab pattern exactly.
 * @startingPoint section="Components" subtitle="Tab bar with count badges" viewport="700x80"
 */
export interface TabsProps {
  children: React.ReactNode;
  selectedId?: string;
  onChange?: (id: string) => void;
  size?: 'small' | 'large';
  style?: React.CSSProperties;
}
export function Tabs(props: TabsProps): JSX.Element;

export interface TabProps {
  id?: string;
  selected?: boolean;
  disabled?: boolean;
  children: React.ReactNode;
  count?: number;
  size?: 'small' | 'large';
  onClick?: () => void;
  style?: React.CSSProperties;
}
export function Tab(props: TabProps): JSX.Element;

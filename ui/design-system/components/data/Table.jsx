export function Table({ columns = [], rows = [], onRowClick, style, ...rest }) {
  const wrapS = { width: '100%', overflowX: 'auto', ...style };
  const gridCols = columns.map(c => c.width || '1fr').join(' ');
  const headerS = { display: 'grid', gridTemplateColumns: gridCols, gap: '0', padding: '8px 0', borderBottom: '1px solid var(--color-keyline-default)' };
  const thS = { font: 'var(--type-label-sm)', textTransform: 'uppercase', letterSpacing: 'var(--tracking-label)', color: 'var(--color-text-lighter)', padding: '0 8px' };
  const rowS = { display: 'grid', gridTemplateColumns: gridCols, gap: '0', padding: '12px 0', borderBottom: '1px solid var(--color-keyline-default)', cursor: onRowClick ? 'pointer' : 'default', transition: 'background 100ms' };
  const cellS = { font: 'var(--type-body-md)', color: 'var(--color-text-default)', padding: '0 8px', display: 'flex', alignItems: 'center' };
  return React.createElement('div', { style: wrapS, ...rest },
    React.createElement('div', { style: headerS }, columns.map((c, i) => React.createElement('div', { key: i, style: thS }, c.label))),
    rows.map((row, ri) => React.createElement('div', { key: ri, style: rowS, onClick: () => onRowClick && onRowClick(row, ri) },
      columns.map((c, ci) => React.createElement('div', { key: ci, style: cellS }, c.render ? c.render(row, ri) : row[c.key]))
    ))
  );
}

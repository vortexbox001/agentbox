export function Table({ columns = [], rows = [], onRowClick, fullBleed = false, style, ...rest }) {
  // Two layouts:
  //  - default (detail page, single object): content inset from the edges, hairline
  //    header + row rules, no vertical dividers.
  //  - fullBleed (object-overview / list, the Dagster Runs pattern): horizontal rules
  //    run edge to edge, a 2px header rule, per-column vertical dividers, and the first
  //    and last cells inset 24px so cell content still lines up with surrounding copy.
  const gridCols = columns.map(c => c.width || '1fr').join(' ');
  const kl = '1px solid var(--color-keyline-default)';
  const last = columns.length - 1;
  const wrapS = { width: '100%', overflowX: 'auto', ...style };
  const pad = (i) => {
    const l = i === 0 ? (fullBleed ? 24 : 16) : 16;
    const r = i === last ? (fullBleed ? 24 : 16) : 16;
    return { l, r };
  };
  const divider = (i) => (fullBleed && i !== last ? kl : undefined);
  const headerS = { display: 'grid', gridTemplateColumns: gridCols, borderBottom: fullBleed ? '2px solid var(--color-border-default)' : kl };
  const rowS = { display: 'grid', gridTemplateColumns: gridCols, borderBottom: kl, cursor: onRowClick ? 'pointer' : 'default', transition: 'background 100ms' };
  const thS = (i) => { const p = pad(i); return { font: 'var(--type-label-sm)', textTransform: 'uppercase', letterSpacing: 'var(--tracking-label)', color: 'var(--color-text-lighter)', display: 'flex', alignItems: 'center', padding: '8px ' + p.r + 'px 8px ' + p.l + 'px', borderRight: divider(i) }; };
  const cellS = (i) => { const p = pad(i); return { font: 'var(--type-body-md)', color: 'var(--color-text-default)', display: 'flex', alignItems: 'center', minWidth: 0, padding: '12px ' + p.r + 'px 12px ' + p.l + 'px', borderRight: divider(i) }; };
  return React.createElement('div', { style: wrapS, ...rest },
    React.createElement('div', { style: headerS }, columns.map((c, i) => React.createElement('div', { key: i, style: thS(i) }, c.label))),
    rows.map((row, ri) => React.createElement('div', { key: ri, style: rowS, onClick: () => onRowClick && onRowClick(row, ri) },
      columns.map((c, ci) => React.createElement('div', { key: ci, style: cellS(ci) }, c.render ? c.render(row, ri) : row[c.key]))
    ))
  );
}

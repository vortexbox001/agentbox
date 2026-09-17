export function Pagination({ page = 1, pages = 1, onChange, style, ...rest }) {
  const wrap = { display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '16px', fontFamily: 'var(--font-default)', ...style };
  const btn = (disabled) => ({
    fontFamily: 'var(--font-default)', fontSize: '14px', lineHeight: '20px', fontWeight: 600,
    padding: '8px 16px', borderRadius: '8px',
    border: '1px solid var(--color-border-default)', background: 'none',
    color: disabled ? 'var(--color-text-light)' : 'var(--color-text-default)',
    cursor: disabled ? 'default' : 'pointer', opacity: disabled ? 0.5 : 1,
    transition: 'color 100ms, border-color 100ms',
  });
  const indicator = { fontSize: '14px', lineHeight: '20px', color: 'var(--color-text-light)' };
  const prevDisabled = page <= 1;
  const nextDisabled = page >= pages;
  return React.createElement('nav', { 'aria-label': 'Pagination', style: wrap, ...rest },
    React.createElement('button', {
      type: 'button', 'aria-disabled': prevDisabled, disabled: prevDisabled, style: btn(prevDisabled),
      onClick: onChange && !prevDisabled ? () => onChange(page - 1) : undefined,
    }, 'Prev'),
    React.createElement('span', { style: indicator }, `Page ${page} of ${pages}`),
    React.createElement('button', {
      type: 'button', 'aria-disabled': nextDisabled, disabled: nextDisabled, style: btn(nextDisabled),
      onClick: onChange && !nextDisabled ? () => onChange(page + 1) : undefined,
    }, 'Next'),
  );
}

export function Select({ label, value, onChange, options = [], disabled, style, ...rest }) {
  const wrapS = { display: 'flex', flexDirection: 'column', gap: '4px', ...style };
  const labelS = { font: 'var(--type-label)', textTransform: 'uppercase', letterSpacing: 'var(--tracking-label)', color: 'var(--color-text-light)' };
  const selS = {
    padding: '8px 32px 8px 12px', borderRadius: '8px',
    background: 'var(--color-background-default)',
    border: '1px solid var(--color-border-default)',
    font: 'var(--type-body-md)', color: 'var(--color-text-default)',
    outline: 'none', width: '100%', cursor: 'pointer',
    appearance: 'none', WebkitAppearance: 'none',
    backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23677488' stroke-width='2' stroke-linecap='round'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E\")",
    backgroundRepeat: 'no-repeat', backgroundPosition: 'right 10px center',
    opacity: disabled ? 0.5 : 1,
  };
  return React.createElement('div', { style: wrapS },
    label && React.createElement('label', { style: labelS }, label),
    React.createElement('select', { value, onChange: e => onChange && onChange(e.target.value), disabled, style: selS, ...rest },
      options.map(o => React.createElement('option', { key: typeof o === 'string' ? o : o.value, value: typeof o === 'string' ? o : o.value }, typeof o === 'string' ? o : o.label))
    )
  );
}

export function TextInput({ label, value, onChange, placeholder, disabled, error, type = 'text', style, inputStyle, ...rest }) {
  const wrapS = { display: 'flex', flexDirection: 'column', gap: '4px', ...style };
  const labelS = { font: 'var(--type-label)', textTransform: 'uppercase', letterSpacing: 'var(--tracking-label)', color: 'var(--color-text-light)' };
  const inputS = {
    padding: '8px 12px', borderRadius: '8px',
    background: 'var(--color-background-default)',
    border: '1px solid ' + (error ? 'var(--color-accent-red)' : 'var(--color-border-default)'),
    font: 'var(--type-body-md)', color: 'var(--color-text-default)',
    outline: 'none', width: '100%', transition: 'border-color 150ms',
    opacity: disabled ? 0.5 : 1, ...inputStyle,
  };
  return React.createElement('div', { style: wrapS },
    label && React.createElement('label', { style: labelS }, label),
    React.createElement('input', { type, value, onChange: e => onChange && onChange(e.target.value), placeholder, disabled, style: inputS, ...rest }),
    error && typeof error === 'string' && React.createElement('span', { style: { font: 'var(--type-body-xs)', color: 'var(--color-text-red)' } }, error)
  );
}

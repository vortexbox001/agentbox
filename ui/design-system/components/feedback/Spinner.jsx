export function Spinner({ size = 20, color, style, ...rest }) {
  const s = {
    width: size + 'px', height: size + 'px',
    border: '2px solid var(--color-border-default)',
    borderTopColor: color || 'var(--color-accent-teal)',
    borderRadius: '50%',
    animation: 'ab-spin 0.6s linear infinite',
    display: 'inline-block', flexShrink: 0, ...style,
  };
  return React.createElement('span', { style: s, ...rest });
}

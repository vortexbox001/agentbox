export function Card({ children, interactive, style, onClick, ...rest }) {
  const s = {
    backgroundColor: 'var(--color-background-default)',
    border: '1px solid var(--color-border-default)',
    borderRadius: '8px', padding: '16px',
    transition: 'border-color 150ms, box-shadow 150ms',
    cursor: interactive ? 'pointer' : 'default', ...style,
  };
  return React.createElement('div', { style: s, onClick, ...rest }, children);
}

export function Alert({ intent = 'info', title, children, style, ...rest }) {
  const colors = {
    info: { border: 'var(--color-accent-teal)', bg: 'var(--color-translucent-teal12)' },
    warning: { border: 'var(--color-accent-yellow)', bg: 'var(--color-background-yellow)' },
    error: { border: 'var(--color-accent-red)', bg: 'var(--color-background-red)' },
    success: { border: 'var(--color-accent-green)', bg: 'var(--color-background-green)' },
  };
  const c = colors[intent] || colors.info;
  const s = { borderRadius: '8px', padding: '12px 16px', backgroundColor: c.bg, borderLeft: '3px solid ' + c.border, ...style };
  return React.createElement('div', { style: s, role: 'alert', ...rest },
    title && React.createElement('div', { style: { font: 'var(--type-body-md)', fontWeight: 600, color: 'var(--color-text-default)', marginBottom: '4px' } }, title),
    children && React.createElement('div', { style: { font: 'var(--type-body-sm)', color: 'var(--color-text-light)' } }, children)
  );
}

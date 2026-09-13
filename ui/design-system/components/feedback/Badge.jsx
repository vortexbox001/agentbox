export function Badge({ label, intent = 'default', style, ...rest }) {
  const colors = {
    running: { bg: 'var(--color-translucent-teal12)', color: 'var(--color-accent-teal)', border: 'var(--color-translucent-teal20)' },
    success: { bg: 'var(--color-background-green)', color: 'var(--color-text-green)', border: 'transparent' },
    error: { bg: 'var(--color-background-red)', color: 'var(--color-text-red)', border: 'transparent' },
    warning: { bg: 'var(--color-background-yellow)', color: 'var(--color-text-yellow)', border: 'transparent' },
    queued: { bg: 'var(--color-background-gray)', color: 'var(--color-text-lighter)', border: 'transparent' },
    scheduled: { bg: 'var(--color-background-lime)', color: 'var(--color-text-lime)', border: 'transparent' },
    default: { bg: 'var(--color-background-gray)', color: 'var(--color-text-light)', border: 'transparent' },
    primary: { bg: 'var(--color-translucent-teal12)', color: 'var(--color-text-teal)', border: 'transparent' },
    lime: { bg: 'var(--color-background-lime)', color: 'var(--color-text-lime)', border: 'transparent' },
  };
  const c = colors[intent] || colors.default;
  const s = {
    display: 'inline-flex', alignItems: 'center', gap: '4px',
    padding: '2px 8px', borderRadius: '4px', fontSize: '12px',
    fontWeight: 500, fontFamily: 'var(--font-mono)', lineHeight: '18px',
    backgroundColor: c.bg, color: c.color,
    border: '1px solid ' + c.border,
    whiteSpace: 'nowrap', ...style,
  };
  return React.createElement('span', { style: s, ...rest }, label);
}

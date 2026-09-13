export function Button({ children, intent, outlined, disabled, loading, icon, rightIcon, onClick, style, className, ...rest }) {
  const base = {
    alignItems: 'center',
    border: 'none',
    borderRadius: '8px',
    cursor: disabled ? 'default' : 'pointer',
    display: 'inline-flex',
    flexDirection: 'row',
    fontFamily: 'var(--font-default)',
    fontSize: '14px',
    fontWeight: 'normal',
    lineHeight: '20px',
    padding: '6px 12px',
    transition: 'background-color 100ms, box-shadow 150ms, filter 100ms, opacity 150ms',
    userSelect: 'none',
    whiteSpace: 'nowrap',
    gap: '6px',
    opacity: disabled ? 0.5 : 1,
    textDecoration: 'none',
    ...style,
  };

  const getColors = () => {
    if (outlined) {
      const map = {
        primary: { stroke: 'var(--color-border-default)', text: 'var(--color-accent-primary)', bg: 'transparent', hoverBg: 'var(--color-background-gray)' },
        danger: { stroke: 'var(--color-accent-red)', text: 'var(--color-accent-red)', bg: 'transparent', hoverBg: 'var(--color-background-red)' },
        success: { stroke: 'var(--color-accent-green)', text: 'var(--color-accent-green)', bg: 'transparent', hoverBg: 'var(--color-background-green)' },
      };
      const c = map[intent] || { stroke: 'var(--color-border-default)', text: 'var(--color-accent-primary)', bg: 'transparent', hoverBg: 'var(--color-background-gray)' };
      return { backgroundColor: c.bg, color: c.text, boxShadow: c.stroke + ' inset 0px 0px 0px 1px' };
    }
    const map = {
      primary: { bg: 'var(--color-accent-primary)', text: 'var(--color-accent-reversed)', stroke: 'transparent' },
      danger: { bg: 'var(--color-accent-red)', text: 'var(--color-always-white)', stroke: 'transparent' },
      success: { bg: 'var(--color-accent-green)', text: 'var(--color-always-white)', stroke: 'transparent' },
      warning: { bg: 'var(--color-accent-yellow)', text: 'var(--color-always-white)', stroke: 'transparent' },
    };
    const c = map[intent] || { bg: 'transparent', text: 'var(--color-text-default)', stroke: 'var(--color-border-default)' };
    return { backgroundColor: c.bg, color: c.text, boxShadow: c.stroke + ' inset 0px 0px 0px 1px' };
  };

  const colors = getColors();
  const merged = { ...base, ...colors, ...style };

  return React.createElement('button', {
    disabled: disabled || loading,
    onClick,
    className,
    style: merged,
    ...rest,
  }, icon, children && React.createElement('span', { style: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, children), rightIcon);
}

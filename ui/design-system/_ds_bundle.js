/* @ds-bundle: {"format":4,"namespace":"AgentBoxDesignSystem_463fbd","components":[{"name":"Button","sourcePath":"components/buttons/Button.jsx"},{"name":"Table","sourcePath":"components/data/Table.jsx"},{"name":"Alert","sourcePath":"components/feedback/Alert.jsx"},{"name":"Badge","sourcePath":"components/feedback/Badge.jsx"},{"name":"RunStatusTag","sourcePath":"components/feedback/RunStatusTag.jsx"},{"name":"SchedulePill","sourcePath":"components/feedback/SchedulePill.jsx"},{"name":"Spinner","sourcePath":"components/feedback/Spinner.jsx"},{"name":"StatusDot","sourcePath":"components/feedback/StatusDot.jsx"},{"name":"Checkbox","sourcePath":"components/forms/Checkbox.jsx"},{"name":"Select","sourcePath":"components/forms/Select.jsx"},{"name":"TextInput","sourcePath":"components/forms/TextInput.jsx"},{"name":"Toggle","sourcePath":"components/forms/Toggle.jsx"},{"name":"Card","sourcePath":"components/layout/Card.jsx"},{"name":"Dialog","sourcePath":"components/layout/Dialog.jsx"},{"name":"Tabs","sourcePath":"components/navigation/Tabs.jsx"},{"name":"Tab","sourcePath":"components/navigation/Tabs.jsx"},{"name":"Pagination","sourcePath":"components/navigation/Pagination.jsx"}],"sourceHashes":{"components/buttons/Button.jsx":"e5c09169e13c","components/data/Table.jsx":"ec89ce49f825","components/feedback/Alert.jsx":"a8e9b189d966","components/feedback/Badge.jsx":"dcd2e315e7ee","components/feedback/RunStatusTag.jsx":"9bbfb16297bc","components/feedback/SchedulePill.jsx":"fd6ce3d3d2d6","components/feedback/Spinner.jsx":"ec7ee75319fc","components/feedback/StatusDot.jsx":"a238cf172490","components/forms/Checkbox.jsx":"1b36a86a1d79","components/forms/Select.jsx":"9344fce9702f","components/forms/TextInput.jsx":"a31075e0a82c","components/forms/Toggle.jsx":"9073dbbfcfd8","components/layout/Card.jsx":"d9a3d477352c","components/layout/Dialog.jsx":"3f642a39861e","components/navigation/Tabs.jsx":"6acb218ddf74","static/dropdown.js":"dc2966e327c9","components/navigation/Pagination.jsx":"e70ca85c42e2"},"inlinedExternals":[],"unexposedExports":[{"name":"enhanceSelect","sourcePath":"static/dropdown.js"},{"name":"enhanceSelects","sourcePath":"static/dropdown.js"}]} */

(() => {

const __ds_ns = (window.AgentBoxDesignSystem_463fbd = window.AgentBoxDesignSystem_463fbd || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/buttons/Button.jsx
try { (() => {
function Button({
  children,
  intent,
  outlined,
  disabled,
  loading,
  icon,
  rightIcon,
  onClick,
  style,
  className,
  ...rest
}) {
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
    ...style
  };
  const getColors = () => {
    if (outlined) {
      const map = {
        primary: {
          stroke: 'var(--color-border-default)',
          text: 'var(--color-accent-primary)',
          bg: 'transparent',
          hoverBg: 'var(--color-background-gray)'
        },
        danger: {
          stroke: 'var(--color-accent-red)',
          text: 'var(--color-accent-red)',
          bg: 'transparent',
          hoverBg: 'var(--color-background-red)'
        },
        success: {
          stroke: 'var(--color-accent-green)',
          text: 'var(--color-accent-green)',
          bg: 'transparent',
          hoverBg: 'var(--color-background-green)'
        }
      };
      const c = map[intent] || {
        stroke: 'var(--color-border-default)',
        text: 'var(--color-accent-primary)',
        bg: 'transparent',
        hoverBg: 'var(--color-background-gray)'
      };
      return {
        backgroundColor: c.bg,
        color: c.text,
        boxShadow: c.stroke + ' inset 0px 0px 0px 1px'
      };
    }
    const map = {
      primary: {
        bg: 'var(--color-accent-primary)',
        text: 'var(--color-accent-reversed)',
        stroke: 'transparent'
      },
      danger: {
        bg: 'var(--color-accent-red)',
        text: 'var(--color-always-white)',
        stroke: 'transparent'
      },
      success: {
        bg: 'var(--color-accent-green)',
        text: 'var(--color-always-white)',
        stroke: 'transparent'
      },
      warning: {
        bg: 'var(--color-accent-yellow)',
        text: 'var(--color-always-white)',
        stroke: 'transparent'
      }
    };
    const c = map[intent] || {
      bg: 'transparent',
      text: 'var(--color-text-default)',
      stroke: 'var(--color-border-default)'
    };
    return {
      backgroundColor: c.bg,
      color: c.text,
      boxShadow: c.stroke + ' inset 0px 0px 0px 1px'
    };
  };
  const colors = getColors();
  const merged = {
    ...base,
    ...colors,
    ...style
  };
  return React.createElement('button', {
    disabled: disabled || loading,
    onClick,
    className,
    style: merged,
    ...rest
  }, icon, children && React.createElement('span', {
    style: {
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    }
  }, children), rightIcon);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/buttons/Button.jsx", error: String((e && e.message) || e) }); }

// components/data/Table.jsx
try { (() => {
function Table({
  columns = [],
  rows = [],
  onRowClick,
  fullBleed = false,
  style,
  ...rest
}) {
  // Two layouts:
  //  - default (detail page, single object): content inset from the edges, hairline
  //    header + row rules, no vertical dividers.
  //  - fullBleed (object-overview / list, the Dagster Runs pattern): horizontal rules
  //    run edge to edge, a 2px header rule, per-column vertical dividers, and the first
  //    and last cells inset 24px so cell content still lines up with surrounding copy.
  const gridCols = columns.map(c => c.width || '1fr').join(' ');
  const kl = '1px solid var(--color-keyline-default)';
  const last = columns.length - 1;
  const wrapS = {
    width: '100%',
    overflowX: 'auto',
    ...style
  };
  const pad = i => {
    const l = i === 0 ? fullBleed ? 24 : 16 : 16;
    const r = i === last ? fullBleed ? 24 : 16 : 16;
    return {
      l,
      r
    };
  };
  const divider = i => fullBleed && i !== last ? kl : undefined;
  const headerS = {
    display: 'grid',
    gridTemplateColumns: gridCols,
    borderBottom: fullBleed ? '2px solid var(--color-border-default)' : kl
  };
  const rowS = {
    display: 'grid',
    gridTemplateColumns: gridCols,
    borderBottom: kl,
    cursor: onRowClick ? 'pointer' : 'default',
    transition: 'background 100ms'
  };
  const thS = i => {
    const p = pad(i);
    return {
      font: 'var(--type-label-sm)',
      textTransform: 'uppercase',
      letterSpacing: 'var(--tracking-label)',
      color: 'var(--color-text-lighter)',
      display: 'flex',
      alignItems: 'center',
      padding: '8px ' + p.r + 'px 8px ' + p.l + 'px',
      borderRight: divider(i)
    };
  };
  const cellS = i => {
    const p = pad(i);
    return {
      font: 'var(--type-body-md)',
      color: 'var(--color-text-default)',
      display: 'flex',
      alignItems: 'center',
      minWidth: 0,
      padding: '12px ' + p.r + 'px 12px ' + p.l + 'px',
      borderRight: divider(i)
    };
  };
  return React.createElement('div', {
    style: wrapS,
    ...rest
  }, React.createElement('div', {
    style: headerS
  }, columns.map((c, i) => React.createElement('div', {
    key: i,
    style: thS(i)
  }, c.label))), rows.map((row, ri) => React.createElement('div', {
    key: ri,
    style: rowS,
    onClick: () => onRowClick && onRowClick(row, ri)
  }, columns.map((c, ci) => React.createElement('div', {
    key: ci,
    style: cellS(ci)
  }, c.render ? c.render(row, ri) : row[c.key])))));
}
Object.assign(__ds_scope, { Table });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/Table.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Alert.jsx
try { (() => {
function Alert({
  intent = 'info',
  title,
  children,
  style,
  ...rest
}) {
  const colors = {
    info: {
      border: 'var(--color-accent-teal)',
      bg: 'var(--color-translucent-teal12)'
    },
    warning: {
      border: 'var(--color-accent-yellow)',
      bg: 'var(--color-background-yellow)'
    },
    error: {
      border: 'var(--color-accent-red)',
      bg: 'var(--color-background-red)'
    },
    success: {
      border: 'var(--color-accent-green)',
      bg: 'var(--color-background-green)'
    }
  };
  const c = colors[intent] || colors.info;
  const s = {
    borderRadius: '8px',
    padding: '12px 16px',
    backgroundColor: c.bg,
    borderLeft: '3px solid ' + c.border,
    ...style
  };
  return React.createElement('div', {
    style: s,
    role: 'alert',
    ...rest
  }, title && React.createElement('div', {
    style: {
      font: 'var(--type-body-md)',
      fontWeight: 600,
      color: 'var(--color-text-default)',
      marginBottom: '4px'
    }
  }, title), children && React.createElement('div', {
    style: {
      font: 'var(--type-body-sm)',
      color: 'var(--color-text-light)'
    }
  }, children));
}
Object.assign(__ds_scope, { Alert });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Alert.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Badge.jsx
try { (() => {
function Badge({
  label,
  intent = 'default',
  style,
  ...rest
}) {
  const colors = {
    running: {
      bg: 'var(--color-translucent-teal12)',
      color: 'var(--color-accent-teal)',
      border: 'var(--color-translucent-teal20)'
    },
    success: {
      bg: 'var(--color-background-green)',
      color: 'var(--color-text-green)',
      border: 'transparent'
    },
    error: {
      bg: 'var(--color-background-red)',
      color: 'var(--color-text-red)',
      border: 'transparent'
    },
    warning: {
      bg: 'var(--color-background-yellow)',
      color: 'var(--color-text-yellow)',
      border: 'transparent'
    },
    queued: {
      bg: 'var(--color-background-gray)',
      color: 'var(--color-text-lighter)',
      border: 'transparent'
    },
    scheduled: {
      bg: 'var(--color-background-lime)',
      color: 'var(--color-text-lime)',
      border: 'transparent'
    },
    default: {
      bg: 'var(--color-background-gray)',
      color: 'var(--color-text-light)',
      border: 'transparent'
    },
    primary: {
      bg: 'var(--color-translucent-teal12)',
      color: 'var(--color-text-teal)',
      border: 'transparent'
    },
    lime: {
      bg: 'var(--color-background-lime)',
      color: 'var(--color-text-lime)',
      border: 'transparent'
    }
  };
  const c = colors[intent] || colors.default;
  const s = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '4px',
    padding: '2px 8px',
    borderRadius: '4px',
    fontSize: '12px',
    fontWeight: 500,
    fontFamily: 'var(--font-mono)',
    lineHeight: '18px',
    backgroundColor: c.bg,
    color: c.color,
    border: '1px solid ' + c.border,
    whiteSpace: 'nowrap',
    ...style
  };
  return React.createElement('span', {
    style: s,
    ...rest
  }, label);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Badge.jsx", error: String((e && e.message) || e) }); }

// components/feedback/RunStatusTag.jsx
try { (() => {
function RunStatusTag({
  status = 'success',
  label,
  style,
  ...rest
}) {
  const map = {
    success: {
      bg: 'var(--color-background-green)',
      dot: 'var(--color-accent-green)'
    },
    failure: {
      bg: 'var(--color-background-red)',
      dot: 'var(--color-accent-red)'
    },
    error: {
      bg: 'var(--color-background-red)',
      dot: 'var(--color-accent-red)'
    },
    started: {
      bg: 'var(--color-background-gray)',
      dot: 'var(--color-text-light)'
    },
    running: {
      bg: 'var(--color-background-gray)',
      dot: 'var(--color-text-light)'
    },
    queued: {
      bg: 'var(--color-background-gray)',
      dot: 'var(--color-text-lighter)'
    },
    canceled: {
      bg: 'var(--color-background-yellow)',
      dot: 'var(--color-accent-yellow)'
    }
  };
  const c = map[status] || map.success;
  const s = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    padding: '3px 9px',
    borderRadius: '8px',
    background: c.bg,
    whiteSpace: 'nowrap',
    ...style
  };
  return React.createElement('span', {
    style: s,
    ...rest
  }, React.createElement('span', {
    style: {
      width: '7px',
      height: '7px',
      borderRadius: '50%',
      background: c.dot,
      flexShrink: 0
    }
  }), React.createElement('span', {
    style: {
      font: 'var(--type-body-sm)',
      color: 'var(--color-text-default)',
      fontWeight: 500
    }
  }, label || status));
}
Object.assign(__ds_scope, { RunStatusTag });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/RunStatusTag.jsx", error: String((e && e.message) || e) }); }

// components/feedback/SchedulePill.jsx
try { (() => {
function SchedulePill({
  type = 'schedule',
  label,
  on = false,
  onToggle,
  style,
  ...rest
}) {
  const stroke = {
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    width: 12,
    height: 12,
    viewBox: '0 0 24 24'
  };
  const icon = type === 'sensor' ? React.createElement('svg', stroke, React.createElement('circle', {
    cx: 12,
    cy: 12,
    r: 2
  }), React.createElement('path', {
    d: 'M7.76 16.24a6 6 0 0 1 0-8.49M16.24 7.76a6 6 0 0 1 0 8.49M4.93 19.07a10 10 0 0 1 0-14.14M19.07 4.93a10 10 0 0 1 0 14.14'
  })) : React.createElement('svg', stroke, React.createElement('circle', {
    cx: 12,
    cy: 12,
    r: 9
  }), React.createElement('polyline', {
    points: '12 7 12 12 15 14'
  }));
  const wrap = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '8px',
    padding: '4px 10px',
    borderRadius: '8px',
    background: 'var(--color-background-gray)',
    minWidth: 0,
    ...style
  };
  const track = {
    width: '22px',
    height: '13px',
    borderRadius: '999px',
    background: on ? 'var(--color-accent-teal)' : 'var(--color-border-default)',
    position: 'relative',
    flexShrink: 0,
    display: 'inline-block',
    cursor: onToggle ? 'pointer' : 'default'
  };
  const knob = {
    position: 'absolute',
    top: '2px',
    [on ? 'right' : 'left']: '2px',
    width: '9px',
    height: '9px',
    borderRadius: '50%',
    background: '#fff'
  };
  return React.createElement('span', {
    style: wrap,
    ...rest
  }, React.createElement('span', {
    style: {
      color: 'var(--color-text-lighter)',
      display: 'inline-flex',
      flexShrink: 0
    }
  }, icon), React.createElement('span', {
    style: {
      font: 'var(--type-body-sm)',
      color: 'var(--color-text-default)',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    }
  }, label), React.createElement('span', {
    style: track,
    onClick: onToggle,
    role: onToggle ? 'switch' : undefined,
    'aria-checked': on
  }, React.createElement('span', {
    style: knob
  })));
}
Object.assign(__ds_scope, { SchedulePill });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/SchedulePill.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Spinner.jsx
try { (() => {
function Spinner({
  size = 20,
  color,
  style,
  ...rest
}) {
  const s = {
    width: size + 'px',
    height: size + 'px',
    border: '2px solid var(--color-border-default)',
    borderTopColor: color || 'var(--color-accent-teal)',
    borderRadius: '50%',
    animation: 'ab-spin 0.6s linear infinite',
    display: 'inline-block',
    flexShrink: 0,
    ...style
  };
  return React.createElement('span', {
    style: s,
    ...rest
  });
}
Object.assign(__ds_scope, { Spinner });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Spinner.jsx", error: String((e && e.message) || e) }); }

// components/feedback/StatusDot.jsx
try { (() => {
function StatusDot({
  status = 'idle',
  size = 8,
  style,
  ...rest
}) {
  const colors = {
    running: 'var(--color-core-teal500)',
    success: 'var(--color-core-green500)',
    error: 'var(--color-core-red500)',
    warning: 'var(--color-core-yellow500)',
    scheduled: 'var(--color-core-lime500)',
    idle: 'var(--color-core-gray400)'
  };
  const glows = {
    running: 'var(--shadow-glow-teal)',
    success: 'none',
    error: 'none'
  };
  const s = {
    width: size + 'px',
    height: size + 'px',
    borderRadius: '50%',
    backgroundColor: colors[status] || colors.idle,
    boxShadow: glows[status] || 'none',
    flexShrink: 0,
    display: 'inline-block',
    ...style
  };
  return React.createElement('span', {
    style: s,
    ...rest
  });
}
Object.assign(__ds_scope, { StatusDot });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/StatusDot.jsx", error: String((e && e.message) || e) }); }

// components/forms/Checkbox.jsx
try { (() => {
function Checkbox({
  checked,
  onChange,
  label,
  disabled,
  style,
  ...rest
}) {
  const wrapS = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    cursor: disabled ? 'default' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    ...style
  };
  const boxS = {
    width: '16px',
    height: '16px',
    borderRadius: '4px',
    flexShrink: 0,
    border: checked ? 'none' : '2px solid var(--color-checkbox-unchecked)',
    backgroundColor: checked ? 'var(--color-checkbox-checked)' : 'transparent',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'all 150ms'
  };
  const checkmark = checked ? React.createElement('svg', {
    width: 10,
    height: 10,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: '#fff',
    strokeWidth: 3,
    strokeLinecap: 'round',
    strokeLinejoin: 'round'
  }, React.createElement('path', {
    d: 'M20 6L9 17l-5-5'
  })) : null;
  return React.createElement('label', {
    style: wrapS,
    ...rest
  }, React.createElement('span', {
    style: boxS
  }, checkmark), label && React.createElement('span', {
    style: {
      font: 'var(--type-body-md)',
      color: 'var(--color-text-default)'
    }
  }, label), React.createElement('input', {
    type: 'checkbox',
    checked,
    onChange: e => onChange && onChange(e.target.checked),
    disabled,
    style: {
      display: 'none'
    }
  }));
}
Object.assign(__ds_scope, { Checkbox });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Checkbox.jsx", error: String((e && e.message) || e) }); }

// components/forms/Select.jsx
try { (() => {
function Select({
  label,
  value,
  onChange,
  options = [],
  disabled,
  style,
  ...rest
}) {
  const wrapS = {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    ...style
  };
  const labelS = {
    font: 'var(--type-label)',
    textTransform: 'uppercase',
    letterSpacing: 'var(--tracking-label)',
    color: 'var(--color-text-light)'
  };
  const selS = {
    padding: '8px 32px 8px 12px',
    borderRadius: '8px',
    background: 'var(--color-background-default)',
    border: '1px solid var(--color-border-default)',
    font: 'var(--type-body-md)',
    color: 'var(--color-text-default)',
    outline: 'none',
    width: '100%',
    cursor: 'pointer',
    appearance: 'none',
    WebkitAppearance: 'none',
    backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23677488' stroke-width='2' stroke-linecap='round'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E\")",
    backgroundRepeat: 'no-repeat',
    backgroundPosition: 'right 10px center',
    opacity: disabled ? 0.5 : 1
  };
  return React.createElement('div', {
    style: wrapS
  }, label && React.createElement('label', {
    style: labelS
  }, label), React.createElement('select', {
    value,
    onChange: e => onChange && onChange(e.target.value),
    disabled,
    style: selS,
    ...rest
  }, options.map(o => React.createElement('option', {
    key: typeof o === 'string' ? o : o.value,
    value: typeof o === 'string' ? o : o.value
  }, typeof o === 'string' ? o : o.label))));
}
Object.assign(__ds_scope, { Select });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Select.jsx", error: String((e && e.message) || e) }); }

// components/forms/TextInput.jsx
try { (() => {
function TextInput({
  label,
  value,
  onChange,
  placeholder,
  disabled,
  error,
  type = 'text',
  style,
  inputStyle,
  ...rest
}) {
  const wrapS = {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    ...style
  };
  const labelS = {
    font: 'var(--type-label)',
    textTransform: 'uppercase',
    letterSpacing: 'var(--tracking-label)',
    color: 'var(--color-text-light)'
  };
  const inputS = {
    padding: '8px 12px',
    borderRadius: '8px',
    background: 'var(--color-background-default)',
    border: '1px solid ' + (error ? 'var(--color-accent-red)' : 'var(--color-border-default)'),
    font: 'var(--type-body-md)',
    color: 'var(--color-text-default)',
    outline: 'none',
    width: '100%',
    transition: 'border-color 150ms',
    opacity: disabled ? 0.5 : 1,
    ...inputStyle
  };
  return React.createElement('div', {
    style: wrapS
  }, label && React.createElement('label', {
    style: labelS
  }, label), React.createElement('input', {
    type,
    value,
    onChange: e => onChange && onChange(e.target.value),
    placeholder,
    disabled,
    style: inputS,
    ...rest
  }), error && typeof error === 'string' && React.createElement('span', {
    style: {
      font: 'var(--type-body-xs)',
      color: 'var(--color-text-red)'
    }
  }, error));
}
Object.assign(__ds_scope, { TextInput });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/TextInput.jsx", error: String((e && e.message) || e) }); }

// components/forms/Toggle.jsx
try { (() => {
function Toggle({
  checked,
  onChange,
  label,
  disabled,
  style,
  ...rest
}) {
  const wrapS = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    cursor: disabled ? 'default' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    ...style
  };
  const trackS = {
    width: '36px',
    height: '20px',
    borderRadius: '9999px',
    position: 'relative',
    backgroundColor: checked ? 'var(--color-core-teal500)' : 'var(--color-core-gray400)',
    transition: 'background-color 150ms',
    flexShrink: 0
  };
  const thumbS = {
    width: '16px',
    height: '16px',
    borderRadius: '50%',
    backgroundColor: '#fff',
    position: 'absolute',
    top: '2px',
    left: checked ? '18px' : '2px',
    transition: 'left 150ms',
    boxShadow: '0 1px 2px rgba(0,0,0,0.2)'
  };
  return React.createElement('label', {
    style: wrapS,
    ...rest
  }, React.createElement('span', {
    style: trackS
  }, React.createElement('span', {
    style: thumbS
  })), label && React.createElement('span', {
    style: {
      font: 'var(--type-body-md)',
      color: 'var(--color-text-default)'
    }
  }, label), React.createElement('input', {
    type: 'checkbox',
    checked,
    onChange: e => onChange && onChange(e.target.checked),
    disabled,
    style: {
      display: 'none'
    }
  }));
}
Object.assign(__ds_scope, { Toggle });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Toggle.jsx", error: String((e && e.message) || e) }); }

// components/layout/Card.jsx
try { (() => {
function Card({
  children,
  interactive,
  style,
  onClick,
  ...rest
}) {
  const s = {
    backgroundColor: 'var(--color-background-default)',
    border: '1px solid var(--color-border-default)',
    borderRadius: '8px',
    padding: '16px',
    transition: 'border-color 150ms, box-shadow 150ms',
    cursor: interactive ? 'pointer' : 'default',
    ...style
  };
  return React.createElement('div', {
    style: s,
    onClick,
    ...rest
  }, children);
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/layout/Card.jsx", error: String((e && e.message) || e) }); }

// components/layout/Dialog.jsx
try { (() => {
function Dialog({
  open,
  onClose,
  title,
  subtitle,
  children,
  width = 560,
  style,
  ...rest
}) {
  if (!open) return null;
  const backdropS = {
    position: 'fixed',
    inset: 0,
    background: 'var(--color-dialog-background)',
    backdropFilter: 'blur(8px)',
    zIndex: 'var(--z-modal)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center'
  };
  const panelS = {
    width: width + 'px',
    maxWidth: '90vw',
    maxHeight: '85vh',
    background: 'var(--color-background-default)',
    border: '1px solid var(--color-border-hover)',
    borderRadius: '12px',
    display: 'flex',
    flexDirection: 'column',
    boxShadow: 'var(--shadow-lg)',
    ...style
  };
  const headerS = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    padding: '20px 20px 0',
    gap: '12px'
  };
  const closeS = {
    width: '28px',
    height: '28px',
    borderRadius: '6px',
    border: 'none',
    background: 'var(--color-background-gray)',
    color: 'var(--color-text-light)',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '16px',
    flexShrink: 0
  };
  const bodyS = {
    padding: '16px 20px 20px',
    overflowY: 'auto',
    flex: 1
  };
  return React.createElement('div', {
    style: backdropS,
    onClick: e => {
      if (e.target === e.currentTarget) onClose && onClose();
    }
  }, React.createElement('div', {
    style: panelS,
    ...rest
  }, React.createElement('div', {
    style: headerS
  }, React.createElement('div', null, title && React.createElement('div', {
    style: {
      font: 'var(--type-display-sm)',
      color: 'var(--color-text-default)'
    }
  }, title), subtitle && React.createElement('div', {
    style: {
      font: 'var(--type-body-sm)',
      color: 'var(--color-text-light)',
      marginTop: '4px'
    }
  }, subtitle)), React.createElement('button', {
    onClick: onClose,
    style: closeS
  }, '\u00d7')), React.createElement('div', {
    style: bodyS
  }, children)));
}
Object.assign(__ds_scope, { Dialog });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/layout/Dialog.jsx", error: String((e && e.message) || e) }); }

// components/navigation/Tabs.jsx
try { (() => {
function Tabs({
  children,
  selectedId,
  onChange,
  size = 'large',
  style,
  ...rest
}) {
  const s = {
    display: 'flex',
    gap: '16px',
    fontSize: size === 'small' ? '12px' : '14px',
    lineHeight: '20px',
    fontWeight: 600,
    borderBottom: '1px solid var(--color-keyline-default)',
    ...style
  };
  return React.createElement('div', {
    role: 'tablist',
    style: s,
    ...rest
  }, React.Children.map(children, child => {
    if (!React.isValidElement(child)) return null;
    return React.cloneElement(child, {
      selected: child.props.selected || child.props.id === selectedId,
      size,
      ...(onChange ? {
        onClick: () => onChange(child.props.id || '')
      } : {})
    });
  }));
}
function Tab({
  id,
  selected,
  disabled,
  children,
  count,
  size = 'large',
  onClick,
  style,
  ...rest
}) {
  const s = {
    background: 'none',
    border: 'none',
    fontFamily: 'var(--font-default)',
    fontSize: 'inherit',
    lineHeight: 'inherit',
    fontWeight: 600,
    padding: size === 'small' ? '8px 0' : '12px 0',
    color: selected ? 'var(--color-text-default)' : 'var(--color-text-light)',
    boxShadow: selected ? 'var(--color-text-default) 0 -2px 0 inset' : 'transparent 0 -2px 0 inset',
    cursor: disabled ? 'default' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    transition: 'color 100ms, box-shadow 100ms',
    ...style
  };
  const countS = {
    fontFamily: 'var(--font-mono)',
    fontSize: '12px',
    fontWeight: 500,
    padding: '0 5px',
    background: 'var(--color-background-gray)',
    borderRadius: '4px',
    color: 'var(--color-text-default)'
  };
  return React.createElement('button', {
    role: 'tab',
    type: 'button',
    'aria-selected': selected,
    disabled,
    onClick,
    style: s,
    ...rest
  }, children, count !== undefined && React.createElement('span', {
    style: countS
  }, count));
}
Object.assign(__ds_scope, { Tabs, Tab });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/Tabs.jsx", error: String((e && e.message) || e) }); }

// components/navigation/Pagination.jsx
try { (() => {
function Pagination({
  page = 1,
  pages = 1,
  onChange,
  style,
  ...rest
}) {
  const wrap = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '16px',
    fontFamily: 'var(--font-default)',
    ...style
  };
  const btn = disabled => ({
    fontFamily: 'var(--font-default)',
    fontSize: '14px',
    lineHeight: '20px',
    fontWeight: 600,
    padding: '8px 16px',
    borderRadius: '8px',
    border: '1px solid var(--color-border-default)',
    background: 'none',
    color: disabled ? 'var(--color-text-light)' : 'var(--color-text-default)',
    cursor: disabled ? 'default' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    transition: 'color 100ms, border-color 100ms'
  });
  const indicator = {
    fontSize: '14px',
    lineHeight: '20px',
    color: 'var(--color-text-light)'
  };
  const prevDisabled = page <= 1;
  const nextDisabled = page >= pages;
  return React.createElement('nav', {
    'aria-label': 'Pagination',
    style: wrap,
    ...rest
  }, React.createElement('button', {
    type: 'button',
    'aria-disabled': prevDisabled,
    disabled: prevDisabled,
    style: btn(prevDisabled),
    onClick: onChange && !prevDisabled ? () => onChange(page - 1) : undefined
  }, 'Prev'), React.createElement('span', {
    style: indicator
  }, `Page ${page} of ${pages}`), React.createElement('button', {
    type: 'button',
    'aria-disabled': nextDisabled,
    disabled: nextDisabled,
    style: btn(nextDisabled),
    onClick: onChange && !nextDisabled ? () => onChange(page + 1) : undefined
  }, 'Next'));
}
Object.assign(__ds_scope, { Pagination });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/Pagination.jsx", error: String((e && e.message) || e) }); }

// static/dropdown.js
try { (() => {
// Custom dropdown — a progressive enhancement over a native <select>.
//
// enhanceSelect(select) keeps the <select> in the DOM as the value store and
// event source (visually hidden) and layers a keyboard-operable trigger plus a
// listbox panel over it. Choosing an option sets select.value and dispatches a
// bubbling `change`, so everything wired to the select keeps working untouched.
//
// Per-option enhancements read from the backing <option>:
//   data-icon="theme-dark"   → a leading <svg><use href="#theme-dark"></svg>.
//                              The referenced symbol must exist in the document.
//   data-note="EDT -4:00"    → a trailing secondary value, pinned right.
// Panel-level enhancement read from the <select>:
//   data-filter               → a sticky filter input at the top of the panel;
//   data-filter="Search…"       its value is the placeholder (default "Filter…").
//
// Accessibility follows the WAI-ARIA select-only combobox pattern. All colours
// live in app.css classes, not here.

const TYPEAHEAD_RESET_MS = 500;
const MIN_PANEL_PX = 120;
const SVG_NS = "http://www.w3.org/2000/svg";
let uid = 0;
let openDropdown = null; // at most one panel open at a time

function nextId(prefix) {
  uid += 1;
  return `${prefix}-${uid}`;
}
function labelFor(select) {
  if (!select.id) return null;
  const label = document.querySelector(`label[for="${CSS.escape(select.id)}"]`);
  if (!label) return null;
  if (label.contains(select)) return label.querySelector(":scope > span");
  return label;
}
function chevron() {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 12 12");
  svg.setAttribute("aria-hidden", "true");
  svg.classList.add("ax-dropdown-chevron");
  const path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("d", "M3 5l3 3 3-3");
  path.setAttribute("stroke", "currentColor");
  path.setAttribute("stroke-width", "1.4");
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("stroke-linejoin", "round");
  svg.appendChild(path);
  return svg;
}
function iconUse(id, cls) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("width", "16");
  svg.setAttribute("height", "16");
  svg.setAttribute("aria-hidden", "true");
  svg.classList.add("ax-icon");
  if (cls) svg.classList.add(cls);
  const use = document.createElementNS(SVG_NS, "use");
  use.setAttribute("href", "#" + id);
  svg.appendChild(use);
  return svg;
}

// Enhance one <select>. Idempotent: an already-enhanced select is re-synced.
function enhanceSelect(select) {
  if (!select || select.tagName !== "SELECT") return null;
  if (select.axDropdown) {
    select.axDropdown.sync();
    return select.axDropdown;
  }
  const hasFilter = select.hasAttribute("data-filter");
  const filterPlaceholder = select.getAttribute("data-filter") || "Filter\u2026";
  const wrap = document.createElement("div");
  wrap.className = "ax-dropdown";
  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "ax-dropdown-trigger";
  trigger.id = select.id ? `${select.id}-trigger` : nextId("ax-dropdown");
  trigger.setAttribute("role", "combobox");
  trigger.setAttribute("aria-haspopup", "listbox");
  trigger.setAttribute("aria-expanded", "false");
  const valueEl = document.createElement("span");
  valueEl.className = "ax-dropdown-value";
  valueEl.id = `${trigger.id}-value`;
  const panel = document.createElement("div");
  panel.className = "ax-dropdown-panel";
  panel.id = `${trigger.id}-listbox`;
  panel.hidden = true;

  // Filter row (optional) + the option list.
  let filterInput = null;
  if (hasFilter) {
    const fr = document.createElement("div");
    fr.className = "ax-dropdown-filter";
    fr.appendChild(iconUse("search"));
    filterInput = document.createElement("input");
    filterInput.type = "text";
    filterInput.placeholder = filterPlaceholder;
    filterInput.setAttribute("aria-label", filterPlaceholder);
    fr.appendChild(filterInput);
    panel.appendChild(fr);
  }
  const list = document.createElement("ul");
  list.className = "ax-dropdown-list";
  list.style.cssText = "list-style:none;margin:0;padding:0";
  list.setAttribute("role", "listbox");
  list.id = `${trigger.id}-list`;
  panel.appendChild(list);
  const emptyEl = document.createElement("div");
  emptyEl.className = "ax-dropdown-empty";
  emptyEl.textContent = "No matches";
  emptyEl.hidden = true;
  panel.appendChild(emptyEl);
  trigger.setAttribute("aria-controls", list.id);
  const leadWrap = document.createElement("span");
  leadWrap.className = "ax-dropdown-lead";
  leadWrap.style.display = "none";
  trigger.append(leadWrap, valueEl, chevron());
  const sizer = document.createElement("div");
  sizer.className = "ax-dropdown-sizer";
  sizer.setAttribute("aria-hidden", "true");
  const label = labelFor(select);
  if (label) {
    if (!label.id) label.id = `${trigger.id}-label`;
    trigger.setAttribute("aria-labelledby", `${label.id} ${valueEl.id}`);
  } else {
    trigger.setAttribute("aria-labelledby", valueEl.id);
  }
  select.parentNode.insertBefore(wrap, select);
  wrap.append(trigger, panel, sizer, select);
  select.classList.add("ax-dropdown-native");
  select.tabIndex = -1;
  select.setAttribute("aria-hidden", "true");
  let isOpen = false;
  let active = -1;
  let taBuffer = "";
  let taLast = 0;
  let syncQueued = false;
  let query = "";
  const hidden = new Set(); // option indexes filtered out

  const options = () => Array.from(select.options);
  const usable = (o, i) => o && !o.disabled && !hidden.has(i);
  const firstUsable = () => options().findIndex((o, i) => usable(o, i));
  const lastUsable = () => {
    const o = options();
    for (let i = o.length - 1; i >= 0; i--) if (usable(o[i], i)) return i;
    return -1;
  };
  function step(from, dir, count = 1) {
    const opts = options();
    let i = from,
      moved = 0,
      last = -1;
    while (moved < count) {
      i += dir;
      if (i < 0 || i >= opts.length) break;
      if (usable(opts[i], i)) {
        last = i;
        moved++;
      }
    }
    return last < 0 ? from >= 0 && usable(opts[from], from) ? from : firstUsable() : last;
  }
  function liFor(i) {
    return list.querySelector(`[data-i="${i}"]`);
  }
  function setActive(i, scroll) {
    const prev = list.querySelector(".is-active");
    if (prev) prev.classList.remove("is-active");
    active = i;
    const li = i >= 0 ? liFor(i) : null;
    if (li) {
      li.classList.add("is-active");
      trigger.setAttribute("aria-activedescendant", li.id);
      if (scroll) li.scrollIntoView({
        block: "nearest"
      });
    } else {
      trigger.removeAttribute("aria-activedescendant");
    }
  }
  function applyFilter() {
    const q = query.trim().toLowerCase();
    hidden.clear();
    let shown = 0;
    options().forEach((opt, i) => {
      const li = liFor(i);
      const match = !q || opt.text.toLowerCase().includes(q);
      if (match) {
        shown++;
        if (li) li.classList.remove("is-hidden");
      } else {
        hidden.add(i);
        if (li) li.classList.add("is-hidden");
      }
    });
    emptyEl.hidden = shown > 0;
  }
  function sync() {
    syncQueued = false;
    const opts = options();
    sizer.replaceChildren(...opts.map(opt => {
      const line = document.createElement("span");
      // Reserve room for a leading icon + trailing note so the trigger never jumps.
      line.textContent = (opt.dataset.icon ? "\u25a0 " : "") + opt.text + (opt.dataset.note ? "   " + opt.dataset.note : "");
      return line;
    }));
    list.replaceChildren();
    opts.forEach((opt, i) => {
      const li = document.createElement("li");
      li.className = "ax-dropdown-option";
      li.id = `${list.id}-opt-${i}`;
      li.dataset.i = String(i);
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", opt.selected ? "true" : "false");
      if (opt.disabled) li.setAttribute("aria-disabled", "true");
      if (opt.dataset.icon) li.appendChild(iconUse(opt.dataset.icon));
      const lab = document.createElement("span");
      lab.className = "ax-dropdown-opt-label";
      lab.textContent = opt.text;
      li.appendChild(lab);
      if (opt.dataset.note) {
        const note = document.createElement("span");
        note.className = "ax-dropdown-opt-value";
        note.textContent = opt.dataset.note;
        li.appendChild(note);
      }
      li.addEventListener("mousedown", e => e.preventDefault());
      li.addEventListener("click", e => {
        e.preventDefault();
        choose(i);
      });
      li.addEventListener("mousemove", () => {
        if (active !== i && usable(opt, i)) setActive(i, false);
      });
      list.appendChild(li);
    });
    const current = opts[select.selectedIndex];
    valueEl.textContent = current ? current.text : "";
    if (current && current.dataset.icon) {
      leadWrap.replaceChildren(iconUse(current.dataset.icon));
      leadWrap.style.display = "";
    } else {
      leadWrap.replaceChildren();
      leadWrap.style.display = "none";
    }
    const invalid = select.getAttribute("aria-invalid") === "true";
    wrap.classList.toggle("is-invalid", invalid);
    if (invalid) trigger.setAttribute("aria-invalid", "true");else trigger.removeAttribute("aria-invalid");
    trigger.disabled = select.disabled;
    wrap.classList.toggle("is-disabled", select.disabled);
    if (hasFilter) applyFilter();
    if (isOpen) {
      if (select.disabled || !opts.length) close();else setActive(usable(current, select.selectedIndex) ? select.selectedIndex : firstUsable(), true);
    }
  }
  function queueSync() {
    if (!syncQueued) {
      syncQueued = true;
      queueMicrotask(sync);
    }
  }
  function bounds() {
    let top = 0,
      bottom = window.innerHeight;
    for (let el = wrap.parentElement; el; el = el.parentElement) {
      const oy = getComputedStyle(el).overflowY;
      if (oy === "auto" || oy === "scroll") {
        const r = el.getBoundingClientRect();
        top = Math.max(top, r.top);
        bottom = Math.min(bottom, r.bottom);
        break;
      }
    }
    return {
      top,
      bottom
    };
  }
  function place() {
    if (!isOpen) return;
    panel.classList.remove("is-up");
    panel.style.maxHeight = "";
    const r = trigger.getBoundingClientRect();
    const b = bounds();
    const gap = Math.max(0, panel.getBoundingClientRect().top - r.bottom);
    const below = b.bottom - r.bottom - gap;
    const above = r.top - b.top - gap;
    const want = panel.offsetHeight;
    if (want > below && above > below) {
      panel.classList.add("is-up");
      if (want > above) panel.style.maxHeight = `${Math.max(above, MIN_PANEL_PX)}px`;
    } else if (want > below) {
      panel.style.maxHeight = `${Math.max(below, MIN_PANEL_PX)}px`;
    }
  }
  function onDocPointerDown(e) {
    if (!wrap.isConnected || !wrap.contains(e.target)) close();
  }
  function onScroll(e) {
    if (e.target !== panel && e.target !== list) place();
  }
  function open() {
    if (isOpen || trigger.disabled) return;
    sync();
    if (!select.options.length) return;
    if (openDropdown && openDropdown !== api) openDropdown.close();
    isOpen = true;
    openDropdown = api;
    panel.hidden = false;
    wrap.classList.add("is-open");
    trigger.setAttribute("aria-expanded", "true");
    if (hasFilter && filterInput) {
      query = "";
      filterInput.value = "";
      applyFilter();
    }
    const sel = select.selectedIndex;
    setActive(usable(select.options[sel], sel) ? sel : firstUsable(), true);
    place();
    if (hasFilter && filterInput) filterInput.focus();
    document.addEventListener("pointerdown", onDocPointerDown, true);
    window.addEventListener("resize", place);
    window.addEventListener("scroll", onScroll, true);
  }
  function close() {
    if (!isOpen) return;
    isOpen = false;
    if (openDropdown === api) openDropdown = null;
    panel.hidden = true;
    panel.classList.remove("is-up");
    panel.style.maxHeight = "";
    wrap.classList.remove("is-open");
    trigger.setAttribute("aria-expanded", "false");
    setActive(-1, false);
    document.removeEventListener("pointerdown", onDocPointerDown, true);
    window.removeEventListener("resize", place);
    window.removeEventListener("scroll", onScroll, true);
  }
  function choose(i) {
    const opt = select.options[i];
    if (!opt || opt.disabled) return;
    const changed = select.selectedIndex !== i;
    close();
    if (changed) {
      select.selectedIndex = i;
      select.dispatchEvent(new Event("change", {
        bubbles: true
      }));
    }
    sync();
    if (trigger.isConnected) trigger.focus();
  }
  function typeahead(key) {
    const now = Date.now();
    if (now - taLast > TYPEAHEAD_RESET_MS) taBuffer = "";
    taLast = now;
    taBuffer += key.toLowerCase();
    const opts = options();
    if (!opts.length) return -1;
    const repeated = taBuffer.length > 1 && taBuffer.split("").every(c => c === taBuffer[0]);
    const needle = repeated ? taBuffer[0] : taBuffer;
    const from = isOpen ? active : select.selectedIndex;
    const start = repeated || taBuffer.length === 1 ? from + 1 : from;
    for (let n = 0; n < opts.length; n++) {
      const i = ((start + n) % opts.length + opts.length) % opts.length;
      if (usable(opts[i], i) && opts[i].text.trim().toLowerCase().startsWith(needle)) return i;
    }
    return -1;
  }
  function onKeyDown(e) {
    if (trigger.disabled) return;
    const key = e.key;
    const plain = key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey;
    if (!isOpen) {
      if (key === "ArrowDown" || key === "ArrowUp" || key === "Enter" || key === " ") {
        e.preventDefault();
        open();
      } else if (plain && !hasFilter) {
        const i = typeahead(key);
        if (i >= 0) {
          e.preventDefault();
          choose(i);
        }
      }
      return;
    }
    switch (key) {
      case "ArrowDown":
        e.preventDefault();
        setActive(step(active, 1), true);
        break;
      case "ArrowUp":
        e.preventDefault();
        setActive(step(active, -1), true);
        break;
      case "PageDown":
        e.preventDefault();
        setActive(step(active, 1, 10), true);
        break;
      case "PageUp":
        e.preventDefault();
        setActive(step(active, -1, 10), true);
        break;
      case "Home":
        e.preventDefault();
        setActive(firstUsable(), true);
        break;
      case "End":
        e.preventDefault();
        setActive(lastUsable(), true);
        break;
      case "Enter":
        e.preventDefault();
        if (active >= 0) choose(active);else close();
        break;
      case " ":
        if (!hasFilter) {
          e.preventDefault();
          if (active >= 0) choose(active);else close();
        }
        break;
      case "Escape":
        e.preventDefault();
        e.stopPropagation();
        close();
        break;
      case "Tab":
        close();
        break;
      default:
        if (plain && !hasFilter) {
          e.preventDefault();
          const i = typeahead(key);
          if (i >= 0) setActive(i, true);
        }
    }
  }
  trigger.addEventListener("click", e => {
    if (e.detail === 0) return;
    if (isOpen) close();else open();
  });
  wrap.addEventListener("keydown", onKeyDown);
  wrap.addEventListener("focusout", e => {
    if (!wrap.contains(e.relatedTarget)) close();
  });
  select.addEventListener("focus", () => trigger.focus());
  select.addEventListener("change", queueSync);
  if (filterInput) {
    filterInput.addEventListener("input", () => {
      query = filterInput.value;
      applyFilter();
      setActive(firstUsable(), true);
    });
  }
  new MutationObserver(queueSync).observe(select, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: ["aria-invalid", "disabled", "selected", "value"]
  });
  const api = {
    select,
    wrap,
    trigger,
    panel,
    open,
    close,
    sync,
    get isOpen() {
      return isOpen;
    }
  };
  select.axDropdown = api;
  sync();
  return api;
}

// Enhance every `select.ax-select` under `root` (idempotent per select).
function enhanceSelects(root = document) {
  root.querySelectorAll("select.ax-select").forEach(s => enhanceSelect(s));
}
Object.assign(__ds_scope, { enhanceSelect, enhanceSelects });
})(); } catch (e) { __ds_ns.__errors.push({ path: "static/dropdown.js", error: String((e && e.message) || e) }); }

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Table = __ds_scope.Table;

__ds_ns.Alert = __ds_scope.Alert;

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.RunStatusTag = __ds_scope.RunStatusTag;

__ds_ns.SchedulePill = __ds_scope.SchedulePill;

__ds_ns.Spinner = __ds_scope.Spinner;

__ds_ns.StatusDot = __ds_scope.StatusDot;

__ds_ns.Checkbox = __ds_scope.Checkbox;

__ds_ns.Select = __ds_scope.Select;

__ds_ns.TextInput = __ds_scope.TextInput;

__ds_ns.Toggle = __ds_scope.Toggle;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.Dialog = __ds_scope.Dialog;

__ds_ns.Tabs = __ds_scope.Tabs;

__ds_ns.Tab = __ds_scope.Tab;

__ds_ns.Pagination = __ds_scope.Pagination;

})();

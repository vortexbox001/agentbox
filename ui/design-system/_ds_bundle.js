/* @ds-bundle: {"format":4,"namespace":"AgentBoxDesignSystem_463fbd","components":[{"name":"Button","sourcePath":"components/buttons/Button.jsx"},{"name":"Table","sourcePath":"components/data/Table.jsx"},{"name":"Alert","sourcePath":"components/feedback/Alert.jsx"},{"name":"Badge","sourcePath":"components/feedback/Badge.jsx"},{"name":"RunStatusTag","sourcePath":"components/feedback/RunStatusTag.jsx"},{"name":"SchedulePill","sourcePath":"components/feedback/SchedulePill.jsx"},{"name":"Spinner","sourcePath":"components/feedback/Spinner.jsx"},{"name":"StatusDot","sourcePath":"components/feedback/StatusDot.jsx"},{"name":"Checkbox","sourcePath":"components/forms/Checkbox.jsx"},{"name":"Select","sourcePath":"components/forms/Select.jsx"},{"name":"TextInput","sourcePath":"components/forms/TextInput.jsx"},{"name":"Toggle","sourcePath":"components/forms/Toggle.jsx"},{"name":"Card","sourcePath":"components/layout/Card.jsx"},{"name":"Dialog","sourcePath":"components/layout/Dialog.jsx"},{"name":"Tabs","sourcePath":"components/navigation/Tabs.jsx"},{"name":"Tab","sourcePath":"components/navigation/Tabs.jsx"}],"sourceHashes":{"components/buttons/Button.jsx":"e5c09169e13c","components/data/Table.jsx":"ec89ce49f825","components/feedback/Alert.jsx":"a8e9b189d966","components/feedback/Badge.jsx":"dcd2e315e7ee","components/feedback/RunStatusTag.jsx":"9bbfb16297bc","components/feedback/SchedulePill.jsx":"fd6ce3d3d2d6","components/feedback/Spinner.jsx":"ec7ee75319fc","components/feedback/StatusDot.jsx":"a238cf172490","components/forms/Checkbox.jsx":"1b36a86a1d79","components/forms/Select.jsx":"9344fce9702f","components/forms/TextInput.jsx":"a31075e0a82c","components/forms/Toggle.jsx":"9073dbbfcfd8","components/layout/Card.jsx":"d9a3d477352c","components/layout/Dialog.jsx":"3f642a39861e","components/navigation/Tabs.jsx":"6acb218ddf74","ui_kits/agentbox-app/AgentsPage.jsx":"2e0d56ec6305","ui_kits/agentbox-app/Sidebar.jsx":"047eb1e6870c"},"inlinedExternals":[],"unexposedExports":[]} */

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

// ui_kits/agentbox-app/AgentsPage.jsx
try { (() => {
function AgentsPage() {
  const ns = window.AgentBoxDesignSystem_463fbd || {};
  const Badge = ns.Badge || (() => null);
  const StatusDot = ns.StatusDot || (() => null);
  const [tab, setTab] = React.useState('all');
  const agents = [{
    name: 'summarizer-v2',
    model: 'gpt-4o',
    status: 'running',
    runs: 124,
    lastRun: '2m ago',
    schedule: 'Every 30min',
    tokens: '45.2k'
  }, {
    name: 'code-reviewer',
    model: 'claude-3.5-sonnet',
    status: 'success',
    runs: 89,
    lastRun: '1h ago',
    schedule: 'On push',
    tokens: '128k'
  }, {
    name: 'data-cleaner',
    model: 'gpt-4o-mini',
    status: 'error',
    runs: 45,
    lastRun: '3h ago',
    schedule: 'Daily 2am',
    tokens: '12.8k'
  }, {
    name: 'report-writer',
    model: 'gpt-4o',
    status: 'scheduled',
    runs: 67,
    lastRun: '6h ago',
    schedule: 'Weekly Mon',
    tokens: '89.1k'
  }, {
    name: 'ticket-triage',
    model: 'claude-3.5-sonnet',
    status: 'success',
    runs: 201,
    lastRun: '15m ago',
    schedule: 'Every 5min',
    tokens: '340k'
  }, {
    name: 'doc-indexer',
    model: 'gpt-4o-mini',
    status: 'idle',
    runs: 12,
    lastRun: '2d ago',
    schedule: 'Manual',
    tokens: '5.6k'
  }];
  const headerS = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '20px'
  };
  const titleS = {
    font: 'var(--type-display-lg)',
    color: 'var(--color-text-default)'
  };
  const btnS = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    padding: '6px 12px',
    borderRadius: '8px',
    border: 'none',
    background: 'var(--color-accent-primary)',
    color: 'var(--color-accent-reversed)',
    fontSize: '14px',
    fontWeight: 400,
    cursor: 'pointer',
    fontFamily: 'var(--font-default)'
  };
  const tabBarS = {
    display: 'flex',
    gap: '16px',
    borderBottom: '1px solid var(--color-keyline-default)',
    marginBottom: '16px'
  };
  const tabBtnS = active => ({
    background: 'none',
    border: 'none',
    padding: '12px 0',
    fontFamily: 'var(--font-default)',
    fontSize: '14px',
    fontWeight: 600,
    cursor: 'pointer',
    color: active ? 'var(--color-text-default)' : 'var(--color-text-light)',
    boxShadow: active ? 'var(--color-text-default) 0 -2px 0 inset' : 'none'
  });
  const gridHeaderS = {
    display: 'grid',
    gridTemplateColumns: '2fr 1fr 100px 80px 100px 100px',
    gap: '0',
    padding: '8px 12px',
    borderBottom: '1px solid var(--color-keyline-default)'
  };
  const thS = {
    font: 'var(--type-label-sm)',
    textTransform: 'uppercase',
    letterSpacing: 'var(--tracking-label)',
    color: 'var(--color-text-lighter)'
  };
  const rowS = {
    display: 'grid',
    gridTemplateColumns: '2fr 1fr 100px 80px 100px 100px',
    gap: '0',
    padding: '12px',
    borderBottom: '1px solid var(--color-keyline-default)',
    cursor: 'pointer',
    transition: 'background 100ms'
  };
  const nameS = {
    display: 'flex',
    alignItems: 'center',
    gap: '10px'
  };
  const statCards = [{
    label: 'Total Agents',
    value: '6',
    delta: null
  }, {
    label: 'Active Runs',
    value: '2',
    delta: '+1'
  }, {
    label: 'Success Rate',
    value: '94%',
    delta: '+2.1%'
  }, {
    label: 'Tokens Today',
    value: '621k',
    delta: null
  }];
  const statS = {
    background: 'var(--color-background-default)',
    border: '1px solid var(--color-border-default)',
    borderRadius: '8px',
    padding: '16px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px'
  };
  return React.createElement('div', {
    style: {
      padding: '24px',
      height: '100%',
      overflowY: 'auto'
    }
  }, React.createElement('div', {
    style: headerS
  }, React.createElement('span', {
    style: titleS
  }, 'Agents'), React.createElement('button', {
    style: btnS
  }, React.createElement('svg', {
    width: 14,
    height: 14,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2
  }, React.createElement('path', {
    d: 'M12 5v14m-7-7h14'
  })), 'New Agent')),
  // Stat cards
  React.createElement('div', {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(4, 1fr)',
      gap: '12px',
      marginBottom: '20px'
    }
  }, statCards.map((s, i) => React.createElement('div', {
    key: i,
    style: statS
  }, React.createElement('div', {
    style: {
      font: 'var(--type-label-sm)',
      textTransform: 'uppercase',
      letterSpacing: 'var(--tracking-label)',
      color: 'var(--color-text-lighter)'
    }
  }, s.label), React.createElement('div', {
    style: {
      display: 'flex',
      alignItems: 'baseline',
      gap: '8px'
    }
  }, React.createElement('span', {
    style: {
      font: 'var(--type-display-xl)',
      color: 'var(--color-text-default)'
    }
  }, s.value), s.delta && React.createElement('span', {
    style: {
      font: 'var(--type-mono-sm)',
      color: 'var(--color-text-green)'
    }
  }, s.delta))))),
  // Tabs
  React.createElement('div', {
    style: tabBarS
  }, ['all', 'running', 'scheduled', 'failed'].map(t => React.createElement('button', {
    key: t,
    style: tabBtnS(tab === t),
    onClick: () => setTab(t)
  }, t.charAt(0).toUpperCase() + t.slice(1), t === 'all' && React.createElement('span', {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: '12px',
      fontWeight: 500,
      padding: '0 5px',
      background: 'var(--color-background-gray)',
      borderRadius: '4px',
      marginLeft: '6px'
    }
  }, agents.length)))),
  // Table header
  React.createElement('div', {
    style: gridHeaderS
  }, ['Agent', 'Model', 'Status', 'Runs', 'Schedule', 'Last Run'].map(h => React.createElement('div', {
    key: h,
    style: thS
  }, h))),
  // Table rows
  agents.map((a, i) => React.createElement('div', {
    key: i,
    style: rowS
  }, React.createElement('div', {
    style: nameS
  }, React.createElement(StatusDot, {
    status: a.status,
    size: 8
  }), React.createElement('span', {
    style: {
      fontWeight: 500
    }
  }, a.name)), React.createElement('div', {
    style: {
      font: 'var(--type-mono-sm)',
      color: 'var(--color-text-light)'
    }
  }, a.model), React.createElement('div', null, React.createElement(Badge, {
    label: a.status,
    intent: a.status === 'idle' ? 'default' : a.status
  })), React.createElement('div', {
    style: {
      font: 'var(--type-mono-sm)',
      color: 'var(--color-text-default)'
    }
  }, a.runs), React.createElement('div', {
    style: {
      font: 'var(--type-body-sm)',
      color: 'var(--color-text-light)'
    }
  }, a.schedule), React.createElement('div', {
    style: {
      font: 'var(--type-mono-xs)',
      color: 'var(--color-text-lighter)'
    }
  }, a.lastRun))));
}
Object.assign(window, {
  AgentsPage
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/agentbox-app/AgentsPage.jsx", error: String((e && e.message) || e) }); }

// ui_kits/agentbox-app/Sidebar.jsx
try { (() => {
function NavItem({
  icon,
  label,
  active,
  collapsed,
  onClick
}) {
  const s = {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    height: '32px',
    padding: collapsed ? '0' : '0 12px',
    borderRadius: '8px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: active ? 500 : 400,
    transition: 'background 100ms',
    color: active ? 'var(--color-nav-text-selected)' : 'var(--color-nav-text)',
    backgroundColor: active ? 'var(--color-translucent-teal25)' : 'transparent',
    justifyContent: collapsed ? 'center' : 'flex-start',
    width: collapsed ? '32px' : '100%'
  };
  return React.createElement('div', {
    style: s,
    onClick
  }, icon, !collapsed && label);
}
function NavGroup({
  items,
  collapsed,
  activeKey,
  onNav
}) {
  return React.createElement('div', {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '2px',
      width: collapsed ? '32px' : '204px'
    }
  }, items.map(it => React.createElement(NavItem, {
    key: it.key,
    icon: it.icon,
    label: it.label,
    active: activeKey === it.key,
    collapsed,
    onClick: () => onNav(it.key)
  })));
}
function Sidebar({
  activeKey,
  onNav,
  collapsed,
  onToggleCollapse
}) {
  const iconSvg = d => React.createElement('svg', {
    width: 16,
    height: 16,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    style: {
      flexShrink: 0
    }
  }, React.createElement('path', {
    d
  }));
  const topGroups = [{
    items: [{
      key: 'overview',
      label: 'Overview',
      icon: iconSvg('M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4')
    }, {
      key: 'runs',
      label: 'Runs',
      icon: iconSvg('M13 10V3L4 14h7v7l9-11h-7z')
    }]
  }, {
    items: [{
      key: 'agents',
      label: 'Agents',
      icon: iconSvg('M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m3-3.803a4 4 0 110-5.292')
    }, {
      key: 'templates',
      label: 'Templates',
      icon: iconSvg('M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6z')
    }, {
      key: 'schedules',
      label: 'Schedules',
      icon: iconSvg('M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z')
    }]
  }, {
    items: [{
      key: 'deployment',
      label: 'Deployment',
      icon: iconSvg('M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2')
    }]
  }];
  const bottomItems = [{
    key: 'search',
    label: 'Search',
    icon: iconSvg('M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z')
  }, {
    key: 'settings',
    label: 'Settings',
    icon: iconSvg('M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z')
  }];
  const sidebarS = {
    width: collapsed ? '68px' : '240px',
    height: '100%',
    backgroundColor: 'var(--color-nav-background)',
    padding: collapsed ? '16px 2px' : '16px 4px 16px 16px',
    display: 'flex',
    flexDirection: 'column',
    boxShadow: 'inset -1px 0 0 var(--color-keyline-default)',
    transition: 'width 200ms',
    overflow: 'hidden',
    flexShrink: 0
  };
  const logoS = {
    padding: collapsed ? '0 0 12px' : '0 12px 16px',
    display: 'flex',
    alignItems: 'center',
    gap: '8px'
  };
  return React.createElement('div', {
    style: sidebarS
  }, React.createElement('div', {
    style: logoS
  }, collapsed ? React.createElement('img', {
    src: '../../assets/logo.svg',
    alt: 'agentbox',
    style: {
      width: '24px',
      height: '24px',
      objectFit: 'contain'
    }
  }) : React.createElement(React.Fragment, null, React.createElement('img', {
    className: 'ax-lockup-light',
    src: '../../assets/logo-light.svg',
    alt: 'agentbox',
    style: {
      width: '130px',
      height: 'auto',
      objectFit: 'contain'
    }
  }), React.createElement('img', {
    className: 'ax-lockup-dark',
    src: '../../assets/logo-dark.svg',
    alt: 'agentbox',
    style: {
      width: '130px',
      height: 'auto',
      objectFit: 'contain'
    }
  }))), React.createElement('div', {
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      gap: '16px',
      overflowY: 'auto'
    }
  }, topGroups.map((g, i) => React.createElement(NavGroup, {
    key: i,
    items: g.items,
    collapsed,
    activeKey,
    onNav
  }))), React.createElement('div', {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '2px',
      paddingRight: collapsed ? 0 : '12px',
      paddingTop: '8px',
      borderTop: '1px solid rgba(255,255,255,0.06)'
    }
  }, bottomItems.map(it => React.createElement(NavItem, {
    key: it.key,
    icon: it.icon,
    label: it.label,
    collapsed,
    onClick: () => onNav(it.key)
  })), React.createElement(NavItem, {
    icon: iconSvg(collapsed ? 'M9 5l7 7-7 7' : 'M15 19l-7-7 7-7'),
    label: collapsed ? '' : 'Collapse',
    collapsed,
    onClick: onToggleCollapse
  })));
}
Object.assign(window, {
  Sidebar
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/agentbox-app/Sidebar.jsx", error: String((e && e.message) || e) }); }

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

})();

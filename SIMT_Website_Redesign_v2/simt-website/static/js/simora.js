(() => {
  const root = document.querySelector('[data-simora]');
  if (!root) return;
  const launcher = root.querySelector('.simora-launcher');
  const panel = root.querySelector('.simora-panel');
  const close = root.querySelector('.simora-close');
  const form = root.querySelector('#simora-form');
  const input = root.querySelector('#simora-input');
  const messages = root.querySelector('#simora-messages');
  const quick = root.querySelector('#simora-quick');
  let sending = false;
  const conversation = [];
  const mobileViewport = window.matchMedia('(max-width: 560px), (pointer: coarse)');
  const visualViewport = window.visualViewport;

  // iOS Safari changes the visual viewport when its on-screen keyboard opens.
  // Keep the panel within the visible area instead of letting it sit behind the keyboard.
  const syncViewportHeight = () => {
    const height = visualViewport ? visualViewport.height : window.innerHeight;
    root.style.setProperty('--simora-viewport-height', `${Math.round(height)}px`);
  };
  syncViewportHeight();
  window.addEventListener('resize', syncViewportHeight, {passive: true});
  if (visualViewport) {
    visualViewport.addEventListener('resize', syncViewportHeight, {passive: true});
    visualViewport.addEventListener('scroll', syncViewportHeight, {passive: true});
  }

  const open = () => {
    panel.hidden = false;
    panel.setAttribute('aria-hidden', 'false');
    launcher.setAttribute('aria-expanded', 'true');
    // Avoid opening the mobile keyboard just because the visitor opened the chat.
    // Desktop users can type immediately; mobile users tap the 16px input when ready.
    if (!mobileViewport.matches) input.focus();
  };
  const shut = () => {
    panel.hidden = true;
    panel.setAttribute('aria-hidden', 'true');
    launcher.setAttribute('aria-expanded', 'false');
    launcher.focus();
  };
  launcher.addEventListener('click', () => panel.hidden ? open() : shut());
  close.addEventListener('click', shut);
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !panel.hidden) shut();
  });

  const addMessage = (text, kind) => {
    const node = document.createElement('div');
    node.className = `simora-message ${kind}-message`;
    node.textContent = text;
    messages.appendChild(node);
    messages.scrollTop = messages.scrollHeight;
    return node;
  };

  const send = async text => {
    const clean = String(text || '').trim();
    if (!clean || sending) return;
    addMessage(clean, 'user');
    input.value = '';
    quick.hidden = true;
    sending = true;
    const typing = document.createElement('div');
    typing.className = 'simora-typing';
    typing.textContent = 'SIMORA is thinking…';
    messages.appendChild(typing);
    messages.scrollTop = messages.scrollHeight;
    form.querySelector('button').disabled = true;
    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {'Content-Type':'application/json','Accept':'application/json'},
        body: JSON.stringify({message: clean, history: conversation.slice(-12)})
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'I could not send that just now. Please try again.');
      const reply = data.reply || 'Please contact the SIMT team for help.';
      conversation.push({role: 'user', content: clean}, {role: 'assistant', content: reply});
      if (conversation.length > 12) conversation.splice(0, conversation.length - 12);
      addMessage(reply, 'bot');
    } catch (error) {
      addMessage(`${error.message} You can also reach SIMT at simt.consultancy007@gmail.com.`, 'bot');
    } finally {
      typing.remove();
      sending = false;
      form.querySelector('button').disabled = false;
      if (!mobileViewport.matches && !panel.hidden) input.focus();
    }
  };

  form.addEventListener('submit', event => {
    event.preventDefault();
    send(input.value);
  });
  quick.querySelectorAll('button[data-prompt]').forEach(button => {
    button.addEventListener('click', () => send(button.dataset.prompt));
  });
})();

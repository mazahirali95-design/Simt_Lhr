(() => {
  const menuButton = document.querySelector('.menu-toggle');
  const menuPanel = document.getElementById('site-menu');
  if (menuButton && menuPanel) {
    const menuLinks = [...menuPanel.querySelectorAll('a')];
    const toggle = (open, restoreFocus = false) => {
      menuPanel.hidden = !open;
      menuButton.setAttribute('aria-expanded', String(open));
      menuButton.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
      document.body.classList.toggle('menu-open', open);
      if (open) menuLinks[0]?.focus();
      else if (restoreFocus) menuButton.focus();
    };
    menuButton.addEventListener('click', () => toggle(menuPanel.hidden));
    menuLinks.forEach(a => a.addEventListener('click', () => toggle(false)));
    document.addEventListener('keydown', event => {
      if (menuPanel.hidden) return;
      if (event.key === 'Escape') {
        toggle(false, true);
        return;
      }
      if (event.key !== 'Tab' || !menuLinks.length) return;
      const first = menuLinks[0];
      const last = menuLinks[menuLinks.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });
  }

  if ('IntersectionObserver' in window && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    document.documentElement.classList.add('js-motion');
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      }
    }, { threshold: 0.06, rootMargin: '0px 0px 60px 0px' });
    document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
    document.querySelectorAll('.team-grid,.values-grid,.three-columns,.service-grid,.service-list,.process-grid,.projects-list').forEach(group => {
      [...group.querySelectorAll('.reveal')].forEach((item, index) => {
        item.style.setProperty('--reveal-delay', `${Math.min(index, 5) * 75}ms`);
      });
    });
  }


  // Header gains a hairline and soft shadow once the page scrolls.
  const header = document.querySelector('.site-header');
  if (header) {
    const onScroll = () => header.classList.toggle('scrolled', window.scrollY > 8);
    window.addEventListener('scroll', onScroll, {passive:true});
    onScroll();
  }

  // Open the service card that a link such as /services#market-research points to.
  const openFromHash = () => {
    const target = location.hash ? document.getElementById(decodeURIComponent(location.hash.slice(1))) : null;
    if (target && target.tagName === 'DETAILS') target.open = true;
  };
  openFromHash();
  window.addEventListener('hashchange', openFromHash);

  const progress = document.querySelector('.scroll-progress');
  if (progress && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    let framePending = false;
    const updateProgress = () => {
      if (framePending) return;
      framePending = true;
      requestAnimationFrame(() => {
        const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
        const ratio = maxScroll > 0 ? Math.min(1, Math.max(0, window.scrollY / maxScroll)) : 0;
        progress.style.width = `${ratio * 100}%`;
        framePending = false;
      });
    };
    window.addEventListener('scroll', updateProgress, {passive:true});
    window.addEventListener('resize', updateProgress);
    updateProgress();
  }

  const form = document.querySelector('#inquiry-form');
  if (!form) return;

  const params = new URLSearchParams(window.location.search);
  const tabs = [...document.querySelectorAll('.form-tabs .tab')];
  const kindField = document.getElementById('kind');
  const service = document.getElementById('contact-service');
  const audience = document.getElementById('contact-audience');
  const dateField = document.getElementById('preferred-date');
  const status = document.getElementById('form-status');
  const submitButton = document.getElementById('submit-inquiry');
  let sending = false;

  const setKind = kind => {
    const safeKind = kind === 'consultation' ? 'consultation' : 'inquiry';
    kindField.value = safeKind;
    tabs.forEach(tab => {
      const active = tab.dataset.kind === safeKind;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    const shown = safeKind === 'consultation';
    document.querySelectorAll('.only-consultation').forEach(x => { x.hidden = !shown; });
    const panel = document.getElementById('panel-inquiry');
    panel?.setAttribute('aria-labelledby', shown ? 'tab-consultation' : 'tab-inquiry');
    submitButton.innerHTML = shown ? 'Request a consultation <span>↗</span>' : 'Send inquiry <span>↗</span>';
    if (status) { status.textContent = ''; status.classList.remove('error'); }
  };
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => setKind(tab.dataset.kind));
    tab.addEventListener('keydown', event => {
      if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
      event.preventDefault();
      const next = tabs[(index + (event.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
      setKind(next.dataset.kind);
      next.focus();
    });
  });
  setKind(params.get('tab'));

  if (params.has('service')) {
    const candidate = params.get('service');
    if ([...service.options].some(o => o.value === candidate)) service.value = candidate;
  }
  if (params.has('audience')) {
    const candidate = params.get('audience');
    if ([...audience.options].some(o => o.value === candidate)) audience.value = candidate;
  }
  if (dateField) {
    const local = new Date();
    const yyyy = local.getFullYear();
    const mm = String(local.getMonth() + 1).padStart(2, '0');
    const dd = String(local.getDate()).padStart(2, '0');
    dateField.min = `${yyyy}-${mm}-${dd}`;
  }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (sending) return;
    status.textContent = '';
    status.classList.remove('error');
    if (!form.reportValidity()) return;
    sending = true;
    submitButton.disabled = true;
    const former = submitButton.innerHTML;
    submitButton.textContent = 'Sending…';
    const data = Object.fromEntries(new FormData(form).entries());
    try {
      const response = await fetch('/api/inquiries', {
        method: 'POST',
        headers: { 'Content-Type':'application/json', 'Accept':'application/json' },
        body: JSON.stringify(data)
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'The website could not process this request right now. Please try again or email SIMT directly.');
      const submittedKind = kindField.value;
      status.textContent = `Thank you. Your ${submittedKind === 'consultation' ? 'consultation request' : 'inquiry'} is recorded. Reference: ${result.reference}. This is not an appointment confirmation; SIMT will contact you by email.`;
      form.reset();
      setKind(submittedKind);
    } catch (error) {
      status.classList.add('error');
      status.textContent = `${error.message} If needed, email simt.consultancy007@gmail.com directly.`;
    } finally {
      sending = false;
      submitButton.disabled = false;
      submitButton.innerHTML = former;
      status.focus();
    }
  });
})();
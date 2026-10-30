// Header border on scroll
const header = document.querySelector('.site-header');
const onScroll = () => header && header.classList.toggle('scrolled', window.scrollY > 8);
window.addEventListener('scroll', onScroll, { passive: true });
onScroll();

// Reveal on scroll
const items = document.querySelectorAll('.reveal');
if ('IntersectionObserver' in window) {
  const io = new IntersectionObserver((entries) => {
    entries.forEach((en) => {
      if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
  items.forEach((el) => io.observe(el));
} else {
  items.forEach((el) => el.classList.add('in'));
}

// Timeline filter
const filters = document.querySelectorAll('.filter');
const tl = document.querySelectorAll('.tl-item');
filters.forEach((btn) => btn.addEventListener('click', () => {
  const f = btn.dataset.filter;
  filters.forEach((b) => { const on = b === btn; b.classList.toggle('is-on', on); b.setAttribute('aria-pressed', on); });
  let n = 0;
  tl.forEach((li) => {
    const show = f === 'all' || li.dataset.type === f;
    li.classList.toggle('hidden', !show);
    if (show) {
      li.classList.toggle('left', n % 2 === 0);
      li.classList.toggle('right', n % 2 === 1);
      li.classList.add('in');
      n++;
    }
  });
}));

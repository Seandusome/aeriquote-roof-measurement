/* Close the native, keyboard-accessible mobile navigation without changing page routes. */
(() => {
  document.querySelectorAll('.aq-mobile-menu').forEach(menu => {
    const summary=menu.querySelector('summary');
    menu.addEventListener('click',event=>{if(event.target.closest('a'))menu.open=false});
    menu.addEventListener('keydown',event=>{if(event.key==='Escape'&&menu.open){menu.open=false;summary.focus();event.preventDefault()}});
    document.addEventListener('click',event=>{if(menu.open&&!menu.contains(event.target))menu.open=false});
  });
})();

document.addEventListener('DOMContentLoaded', () => {
  // Intersection Observer for showing elements
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('show');
      }
    });
  });

  const hiddenElements = document.querySelectorAll('.hidden');
  hiddenElements.forEach((el) => observer.observe(el));

  // Navbar hide/show on scroll
  let prevScrollpos = window.pageYOffset;
  window.onscroll = function () {
    const currentScrollPos = window.pageYOffset;
    if (prevScrollpos > currentScrollPos) {
      document.getElementById("navbar").style.top = "0";
    } else {
      document.getElementById("navbar").style.top = "-110px";
    }
    prevScrollpos = currentScrollPos;
  };

  // Path animation
  const path = document.getElementById('rocket');
  const pathLength = path.getTotalLength();
  let pathInView = false;

  path.style.strokeDasharray = `${pathLength} ${pathLength}`;
  path.style.strokeDashoffset = pathLength;

  // Function to animate path based on scroll
  function animatePath() {
    if (!pathInView) return;

    const scrollPercentage = (document.documentElement.scrollTop + document.body.scrollTop) / (-document.documentElement.clientHeight * .9);
    const drawLength = pathLength * scrollPercentage;

    path.style.strokeDashoffset = pathLength - drawLength;
  }

  // Intersection Observer for path element
  const pathObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      pathInView = entry.isIntersecting;
      if (pathInView) {
        animatePath(); // Initial call to set the correct state when the path enters view
      }
    });
  });

  pathObserver.observe(path);

  // Scroll event listener
  window.addEventListener('scroll', () => {
    animatePath();

    // Handle scroll-based transformations
    handleScrollTransformations();
  });
});

// Function to handle scroll-based transformations
function handleScrollTransformations() {
  const targets = document.querySelectorAll('.scroll');
  targets.forEach(target => {
    const rate = parseFloat(target.dataset.rate) || 0;
    const rateX = parseFloat(target.dataset.ratex) || 0;
    const rateY = parseFloat(target.dataset.ratey) || 0;
    const pos = window.pageYOffset * rate;

    if (target.dataset.direction === 'horizontal') {
      target.style.transform = `translate3d(${pos}px, 0px, 0px)`;
    } else {
      const posX = window.pageYOffset * rateX;
      const posY = window.pageYOffset * rateY;
      target.style.transform = `translate3d(${posX}px, ${posY}px, 0px)`;
    }
  });
}

document.addEventListener("DOMContentLoaded", function() {
  const scribble = document.getElementById('myPath');
  const follower = document.getElementById('follower');
  const pathDistance = scribble.getTotalLength();

  // Set up the path's length and initial dash properties
  scribble.style.strokeDasharray = pathDistance;
  scribble.style.strokeDashoffset = pathDistance;

  document.addEventListener("scroll", function() {
      const scrollPosition = window.scrollY;
      const maxScroll = document.body.scrollHeight - window.innerHeight;
      const scrollPercentage = Math.min(scrollPosition / maxScroll, 1);
      
      const point = scribble.getPointAtLength(scrollPercentage * pathDistance);

      // Update the follower position
      follower.setAttribute('cx', point.x);
      follower.setAttribute('cy', point.y);

      // Update the path dash offset to reveal the path
      scribble.style.strokeDashoffset = pathDistance - (scrollPercentage * pathDistance);
  });
});
var swiper = new Swiper(".mySwiper", {
  spaceBetween: 30,
  centeredSlides: true,
  autoplay: {
    delay: 2500,
    disableOnInteraction: false,
  },
  pagination: {
    el: ".swiper-pagination",
    clickable: true,
  },
  navigation: {
    nextEl: ".swiper-button-next",
    prevEl: ".swiper-button-prev",
  },
});


var divs = [];
function hovering(ev) {
	divs[0].classList.remove('active');
	divs[1].classList.remove('active');
	ev.target.classList.add('active');

};
document.addEventListener('DOMContentLoaded', function () {
	divs.push(document.getElementById("scratchpad"));
	divs.push(document.getElementById("disable"));

	divs[0].focus();
	divs[0].onclick = function() {
		document.getElementsByTagName('a')[0].click();
	};
	divs[0].onmouseover = hovering;

	divs[1].onclick = function() {
		chrome.extension.getBackgroundPage().rcxMain.inlineDisable();
		window.close();
	};
	divs[1].onmouseover = hovering;
});

window.onkeydown = function(ev) {
	if (ev.code === 'Enter') {
		document.querySelector('.active').click();
	} else if (ev.code === 'ArrowUp' || ev.code === 'ArrowDown') {
		if (divs[0].classList.contains('active')) {
			divs[0].classList.remove('active');
			divs[1].classList.add('active');
		} else {
			divs[1].classList.remove('active');
			divs[0].classList.add('active');
		}
	}
};

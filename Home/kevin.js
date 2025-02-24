let leftcloud = document.getElementById("cloud1");
let rightcloud = document.getElementById("cloud3");
let midcloud = document.getElementById("cloud2");
const fade = Array.from(document.querySelectorAll('.place'));
let studentbutton = document.querySelector('.studentbut');
let teacherbutton = document.querySelector('.teacherbut');
document.addEventListener("DOMContentLoaded", function () {
    leftcloud.classList.add("fade-in-left");
    rightcloud.classList.add("fade-in-right");
    midcloud.classList.add("fade-in-bottom");
    studentbutton.classList.add("fade-in-left");
    teacherbutton.classList.add("fade-in-right");
    fade.forEach(element => {
        element.classList.add("fade-in")
    });
});
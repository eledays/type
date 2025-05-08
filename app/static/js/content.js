var word = null;

var wordElement = document.querySelector('.word');
var answersElement = document.querySelector('.answers');
var loadingElement = document.querySelector('.loading');

addEventListener('DOMContentLoaded', () => {
    fetch('/get_word')
    .then(response => response.json())
    .then(data => {
        word = data;
        loadingElement.style.opacity = 0;
        setTimeout(() => {
            loadingElement.style.display = 'none';
        }, 300);
        wordElement.innerHTML = word.html_word;

        answersElement.innerHTML = '';
        for (let i = 0; i < word.answers.length; i++) {
            let answer = document.createElement('button');
            answer.className = 'answer';
            answer.innerHTML = word.answers[i];
            answersElement.appendChild(answer);

            answer.addEventListener('click', (event) => handleAnswerClick(event, i));
        }
    });
});

function handleAnswerClick(event, i) {
    fetch('/check_word', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({id: word.id, answer: word.answers[i]})
    })
    .then(response => response.json())
    .then(data => {
        if (data.correct) {
            document.body.className = 'correct';
            wordElement.classList.add('shrink');
            setTimeout(() => {
                wordElement.innerHTML = data.full_word;
            }, 200);
            setTimeout(() => {
                document.body.classList.remove('correct');
                parent.postMessage('swipe', '*');
            }, 1000);
        } else {
            alert('Incorrect!');
        }
    });
}
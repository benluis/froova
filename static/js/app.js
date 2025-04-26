document.addEventListener('DOMContentLoaded', function() {
    console.log('App initialized');

    document.querySelectorAll('.tab-button').forEach(button => {
        button.addEventListener('click', () => {
            document.querySelectorAll('.tab-button').forEach(btn => {
                btn.classList.remove('text-green-600', 'border-b-2', 'border-green-500');
                btn.classList.add('text-gray-500');
            });

            button.classList.remove('text-gray-500');
            button.classList.add('text-green-600', 'border-b-2', 'border-green-500');

            const tabName = button.getAttribute('data-tab');
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.add('hidden');
            });
            document.getElementById(`${tabName}-content`).classList.remove('hidden');
        });
    });

    document.getElementById('recipeForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        console.log('Form data:', Object.fromEntries(formData.entries()));

        const allergies = [];
        document.querySelectorAll('input[name="allergen"]:checked').forEach(check => {
            allergies.push(check.value);
        });

        const otherAllergies = document.getElementById('other-allergies').value;
        if (otherAllergies) {
            allergies.push(...otherAllergies.split(',').map(a => a.trim()));
        }

        const diets = [];
        document.querySelectorAll('input[name="diet"]:checked').forEach(check => {
            diets.push(check.value);
        });

        document.getElementById('allergies').value = allergies.length ? allergies.join(', ') : 'None';
        document.getElementById('dietary_preferences').value = diets.join(', ');

        document.getElementById('ingredients-content').innerHTML = `
            <div class="flex justify-center items-center py-10">
                <svg class="animate-spin h-10 w-10 text-green-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
            </div>
        `;

        try {
            const response = await fetch('/submit-recipe', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to process recipe');
            }

            const data = await response.json();
            console.log('API Response:', data);

            displayIngredients(data.ingredients || []);
        } catch (error) {
            console.error('Submission error:', error);
            document.getElementById('ingredients-content').innerHTML = `
                <div class="bg-red-50 border-l-4 border-red-400 p-4 text-red-700">
                    Error: ${error.message || 'Failed to process recipe'}
                </div>
            `;
        }
    });

    function displayIngredients(ingredients) {
        if (!ingredients || ingredients.length === 0) {
            document.getElementById('ingredients-content').innerHTML = `
                <div class="text-center text-gray-500 py-10">
                    No ingredients found. Please check your recipe input.
                </div>
            `;
            return;
        }

        let html = `
        <div class="space-y-4">
            <h3 class="font-semibold text-lg">Recipe Ingredients</h3>
            <div class="grid grid-cols-1 gap-3">
        `;

        ingredients.forEach(ingredient => {
            const cannotEat = ingredient.can_not_eat ? 'bg-red-50 border-red-200' : 'bg-green-50 border-green-200';
            html += `
                <div class="p-3 border ${cannotEat} rounded-lg">
                    <div class="flex justify-between">
                        <div class="font-medium">${ingredient.name}</div>
                        <div class="text-sm text-gray-500">
                            ${ingredient.volume ? ingredient.volume : ''} 
                            ${ingredient.weight ? ingredient.weight : ''}
                        </div>
                    </div>
                    ${ingredient.can_not_eat ? 
                        '<div class="mt-1 text-sm text-red-600">Warning: This ingredient conflicts with your dietary restrictions</div>' : 
                        '<div class="mt-1 text-sm text-green-600">Compatible with your diet</div>'
                    }
                </div>
            `;
        });

        html += `
                </div>
            </div>
        `;

        document.getElementById('ingredients-content').innerHTML = html;

        const alternativesHtml = renderAlternativesTab(ingredients);
        document.getElementById('alternatives-content').innerHTML = alternativesHtml;

        fetchProducts();
    }

    function renderAlternativesTab(ingredients) {
        const problemIngredients = ingredients.filter(i => i.can_not_eat);

        if (problemIngredients.length === 0) {
            return `
                <div class="text-center py-10">
                    <p class="text-green-600">Good news! All ingredients work with your dietary restrictions.</p>
                </div>
            `;
        }

        let html = `
            <div class="space-y-4">
                <h3 class="font-semibold text-lg">Ingredient Alternatives</h3>
                <div class="grid grid-cols-1 gap-3">
        `;

        problemIngredients.forEach(ingredient => {
            html += `
                <div class="p-3 border border-red-200 bg-red-50 rounded-lg">
                    <div class="font-medium">${ingredient.name}</div>
                    <div class="mt-2">
                        <div class="text-sm font-medium text-gray-700">Alternatives:</div>
                        <div class="mt-1 space-y-1">
            `;

            if (ingredient.alternatives && ingredient.alternatives.length > 0) {
                ingredient.alternatives.forEach(alt => {
                    html += `<div class="text-sm bg-white p-1.5 rounded border border-gray-200">${alt}</div>`;
                });
            } else {
                html += `<div class="text-sm text-gray-500 italic">No alternatives found</div>`;
            }

            html += `
                        </div>
                    </div>
                </div>
            `;
        });

        html += `
                </div>
            </div>
        `;

        return html;
    }

    async function fetchProducts() {
        document.getElementById('products-content').innerHTML = `
            <div class="flex justify-center items-center py-10">
                <svg class="animate-spin h-10 w-10 text-green-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
            </div>
        `;

        try {
            const response = await fetch('/api/products');
            if (!response.ok) {
                throw new Error('Failed to load products');
            }

            const products = await response.json();
            renderProducts(products);
        } catch (error) {
            console.error('Error fetching products:', error);
            document.getElementById('products-content').innerHTML = `
                <div class="text-center text-red-500 py-10">
                    Error loading products: ${error.message}
                </div>
            `;
        }
    }

    function renderProducts(products) {
        if (!products || products.length === 0) {
            document.getElementById('products-content').innerHTML = `
                <div class="text-center text-gray-500 py-10">
                    No product information available
                </div>
            `;
            return;
        }

        const storeGroups = {};
        products.forEach(product => {
            const store = product.store || 'Other';
            if (!storeGroups[store]) {
                storeGroups[store] = [];
            }
            storeGroups[store].push(product);
        });

        let html = '<div class="space-y-6">';

        Object.entries(storeGroups).forEach(([store, storeProducts]) => {
            html += `
                <div>
                    <h3 class="font-semibold text-lg mb-3">${store}</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            `;

            storeProducts.forEach(product => {
                html += `
                    <div class="border rounded-lg p-3 flex items-center">
                        ${product.image_url ? 
                            `<img src="${product.image_url}" alt="${product.name}" class="w-16 h-16 object-contain mr-3">` :
                            `<div class="w-16 h-16 bg-gray-100 flex items-center justify-center mr-3">
                                <span class="text-gray-400">No image</span>
                            </div>`
                        }
                        <div class="flex-1">
                            <div class="font-medium">${product.name}</div>
                            <div class="text-sm text-gray-500">${product.type}</div>
                            <div class="text-sm font-bold text-green-700">${product.price}</div>
                        </div>
                    </div>
                `;
            });

            html += `
                    </div>
                </div>
            `;
        });

        html += '</div>';
        document.getElementById('products-content').innerHTML = html;
    }

    // Placeholder functions for other features
    function findAlternatives() {
        // This function can be implemented if needed
    }

    function findProducts() {
        // This function can be implemented if needed
    }

    function showError(message) {
        document.getElementById('ingredients-content').innerHTML = `
            <div class="bg-red-50 border-l-4 border-red-400 p-4 text-red-700">
                ${message}
            </div>
        `;
    }
});
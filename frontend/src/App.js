import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [todos, setTodos] = useState([]);
  const [task, setTask] = useState(""); 

  // Função para carregar os todos da API
  const fetchTodos = async () => {
    const response = await axios.get('https://api.neshiku.com.br/todos');
    setTodos(response.data);
  };

  // Função para adicionar uma nova tarefa
  const addTodo = async () => {
    if (task.trim()) {
      const response = await axios.post('https://api.neshiku.com.br/todos', { text: task });
      setTodos([...todos, response.data]);
      setTask("");
    }
  };

  // Função para marcar a tarefa como concluída
  const toggleComplete = async (id) => {
    const response = await axios.patch(`https://api.neshiku.com.br/todos/${id}`);
    const updatedTodos = todos.map(todo =>
      todo.id === id ? response.data : todo
    );
    setTodos(updatedTodos);
  };

  // Função para excluir a tarefa
  const deleteTodo = async (id) => {
    await axios.delete(`https://api.neshiku.com.br/todos/${id}`);
    setTodos(todos.filter(todo => todo.id !== id));
  };

  // Carregar a lista de todos ao iniciar o componente
  useEffect(() => {
    fetchTodos();
  }, []);

  return (
    <div className="App">
      <h1>Lista de Tarefas</h1>
      <div>
        <input 
          type="text" 
          value={task} 
          onChange={(e) => setTask(e.target.value)} 
          placeholder="Adicione uma tarefa"
        />
        <button onClick={addTodo}>Adicionar</button>
      </div>
      <ul>
        {todos.map((todo) => (
          <li key={todo.id} style={{ textDecoration: todo.completed ? "line-through" : "none" }}>
            <span onClick={() => toggleComplete(todo.id)}>{todo.text}</span>
            <button onClick={() => deleteTodo(todo.id)}>Excluir</button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default App;

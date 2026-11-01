import os, sqlite3, secrets
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE=os.path.dirname(os.path.abspath(__file__))
DB=os.path.join(BASE,'jannah.db')
UPLOAD=os.path.join(BASE,'static','uploads')
ALLOWED={'png','jpg','jpeg','webp'}
app=Flask(__name__)
app.config['SECRET_KEY']=os.environ.get('SECRET_KEY',secrets.token_hex(32))
app.config['MAX_CONTENT_LENGTH']=8*1024*1024
os.makedirs(UPLOAD,exist_ok=True)

def conn():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
    c=conn();
    c.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, name_ar TEXT NOT NULL, name_en TEXT, category TEXT NOT NULL, model TEXT, description_ar TEXT, description_en TEXT, image TEXT, status TEXT DEFAULT 'published', created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
    ''')
    if not c.execute('SELECT 1 FROM users WHERE username=?',('admin',)).fetchone():
        c.execute('INSERT INTO users(username,password) VALUES(?,?)',('admin',generate_password_hash('ChangeMe123!')))
    c.commit(); c.close()

def login_required(f):
    @wraps(f)
    def w(*a,**k):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*a,**k)
    return w

def save_image(file):
    if not file or not file.filename: return None
    ext=file.filename.rsplit('.',1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED: raise ValueError('نوع الصورة غير مدعوم')
    name=f"{secrets.token_hex(12)}.{ext}"
    file.save(os.path.join(UPLOAD,name)); return name

@app.route('/')
def home():
    c=conn(); products=c.execute("SELECT * FROM products WHERE status='published' ORDER BY id DESC").fetchall(); c.close()
    return render_template('index.html', products=[dict(x) for x in products])

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        username=request.form.get('username','').strip(); password=request.form.get('password','')
        c=conn(); u=c.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone(); c.close()
        if u and check_password_hash(u['password'],password):
            session.clear(); session['user_id']=u['id']; session['username']=u['username']; return redirect(url_for('dashboard'))
        flash('بيانات الدخول غير صحيحة','error')
    return render_template('login.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('home'))

@app.route('/admin')
@login_required
def dashboard():
    c=conn(); total=c.execute('SELECT COUNT(*) FROM products').fetchone()[0]; published=c.execute("SELECT COUNT(*) FROM products WHERE status='published'").fetchone()[0]; recent=c.execute('SELECT * FROM products ORDER BY id DESC LIMIT 5').fetchall(); c.close()
    return render_template('dashboard.html',total=total,published=published,recent=recent)

@app.route('/admin/products')
@login_required
def products_admin():
    c=conn(); rows=c.execute('SELECT * FROM products ORDER BY id DESC').fetchall(); c.close(); return render_template('products.html',products=rows)

@app.route('/admin/products/new',methods=['GET','POST'])
@login_required
def product_new():
    if request.method=='POST':
        try: image=save_image(request.files.get('image'))
        except ValueError as e: flash(str(e),'error'); return render_template('product_form.html',p=None)
        c=conn(); c.execute('INSERT INTO products(name_ar,name_en,category,model,description_ar,description_en,image,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(request.form['name_ar'].strip(),request.form.get('name_en','').strip(),request.form['category'],request.form.get('model','').strip(),request.form.get('description_ar','').strip(),request.form.get('description_en','').strip(),image,request.form.get('status','published'),datetime.utcnow().isoformat())); c.commit(); c.close(); flash('تمت إضافة المنتج بنجاح','ok'); return redirect(url_for('products_admin'))
    return render_template('product_form.html',p=None)

@app.route('/admin/products/<int:id>/edit',methods=['GET','POST'])
@login_required
def product_edit(id):
    c=conn(); p=c.execute('SELECT * FROM products WHERE id=?',(id,)).fetchone()
    if not p: c.close(); return ('Not found',404)
    if request.method=='POST':
        image=p['image']
        try:
            if request.files.get('image') and request.files['image'].filename: image=save_image(request.files['image'])
        except ValueError as e: c.close(); flash(str(e),'error'); return render_template('product_form.html',p=p)
        c.execute('UPDATE products SET name_ar=?,name_en=?,category=?,model=?,description_ar=?,description_en=?,image=?,status=? WHERE id=?',(request.form['name_ar'].strip(),request.form.get('name_en','').strip(),request.form['category'],request.form.get('model','').strip(),request.form.get('description_ar','').strip(),request.form.get('description_en','').strip(),image,request.form.get('status','published'),id)); c.commit(); c.close(); flash('تم تحديث المنتج','ok'); return redirect(url_for('products_admin'))
    c.close(); return render_template('product_form.html',p=p)

@app.post('/admin/products/<int:id>/delete')
@login_required
def product_delete(id):
    c=conn(); p=c.execute('SELECT image FROM products WHERE id=?',(id,)).fetchone(); c.execute('DELETE FROM products WHERE id=?',(id,)); c.commit(); c.close()
    if p and p['image']:
        path=os.path.join(UPLOAD,p['image'])
        if os.path.exists(path): os.remove(path)
    flash('تم حذف المنتج','ok'); return redirect(url_for('products_admin'))

@app.post('/admin/products/<int:id>/status')
@login_required
def product_status(id):
    c=conn(); c.execute("UPDATE products SET status=CASE status WHEN 'published' THEN 'draft' ELSE 'published' END WHERE id=?",(id,)); c.commit(); c.close(); return redirect(url_for('products_admin'))

if __name__=='__main__': init_db(); app.run(debug=True,host='0.0.0.0',port=5000)

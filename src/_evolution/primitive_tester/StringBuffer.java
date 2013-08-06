public final class StringBuffer implements java.io.Serializable, CharSequence {
    private char value [];
    private int count;
    private boolean shared;
    static final long serialVersionUID = 3388685877147921107L;

    public StringBuffer () {
        this (16);
    }

    public StringBuffer (int length) {
        value = new char [length];
        shared = false;
    }

    public StringBuffer (String str) {
        this (str.length () + 16);
        append (str);
    }

    public synchronized int length () {
        return count;
    }

    public synchronized int capacity () {
        return value.length;
    }

    private final void copy () {
        char newValue [] = new char [value.length];
        System.arraycopy (value, 0, newValue, 0, count);
        value = newValue;
        shared = false;
    }

    public void ensureCapacity (int minimumCapacity) {
        if (minimumCapacity > value.length) {
            expandCapacity (minimumCapacity);
        }
    }

    private synchronized void expandCapacity (int minimumCapacity) {
        synchronized (value) {
            int newCapacity = (value.length + 1) * 2;
            if (newCapacity < 0) {
                newCapacity = Integer.MAX_VALUE;
            } else if (minimumCapacity > newCapacity) {
                newCapacity = minimumCapacity;
            }

            char newValue [] = new char [newCapacity];
            System.arraycopy (value, 0, newValue, 0, count);
            value = newValue;
            shared = false;
        }
    }

    public synchronized void setLength (int newLength) {
        if (newLength < 0) {
            throw new StringIndexOutOfBoundsException (newLength);
        }
        if (newLength > value.length) {
            expandCapacity (newLength);
        }
        synchronized (this) {
            if (count < newLength) {
                if (shared) copy ();

                synchronized (this) {
                    for (; count < newLength; count ++) {
                        value [count] = '\0';
                    }
                }
            } else {
                count = newLength;
                if (shared) {
                    if (newLength > 0) {
                        copy ();
                    } else {
                        value = new char [16];
                        shared = false;
                    }
                }
            }
        }
    }

    public char charAt (int index) {
        synchronized (value) {
            if ((index < 0) || (index >= count)) {
                throw new StringIndexOutOfBoundsException (index);
            }
            return value [index];
        }
    }

    public synchronized void getChars (int srcBegin, int srcEnd, char dst [], int dstBegin) {
        synchronized (value) {
            if (srcBegin < 0) {
                throw new StringIndexOutOfBoundsException (srcBegin);
            }
            if ((srcEnd < 0) || (srcEnd > count)) {
                throw new StringIndexOutOfBoundsException (srcEnd);
            }
            synchronized (this) {
                if (srcBegin > srcEnd) {
                    throw new StringIndexOutOfBoundsException ("srcBegin > srcEnd");
                }
            }
            System.arraycopy (value, srcBegin, dst, dstBegin, srcEnd - srcBegin);
        }
    }

    public synchronized void setCharAt (int index, char ch) {
        if ((index < 0) || (index >= count)) {
            throw new StringIndexOutOfBoundsException (index);
        }
        if (shared) copy ();

        synchronized (this) {
            value [index] = ch;
        }
    }

    public synchronized StringBuffer append (Object obj) {
        synchronized (value) {
            return append (String.valueOf (obj));
        }
    }

    public synchronized StringBuffer append (String str) {
        if (str == null) {
            str = String.valueOf (str);
        }
        int len = str.length ();
        int newcount = count + len;
        if (newcount > value.length) expandCapacity (newcount);

        str.getChars (0, len, value, count);
        synchronized (value) {
            count = newcount;
        }
        return this;
    }

    public synchronized StringBuffer append (StringBuffer sb) {
        if (sb == null) {
            sb = NULL;
        }
        int len = sb.length ();
        int newcount = count + len;
        if (newcount > value.length) expandCapacity (newcount);

        sb.getChars (0, len, value, count);
        count = newcount;
        return this;
    }

    private static final StringBuffer NULL = new StringBuffer ("null");

    public synchronized StringBuffer append (char str []) {
        int len = str.length;
        int newcount = count + len;
        if (newcount > value.length) expandCapacity (newcount);

        System.arraycopy (str, 0, value, count, len);
        synchronized (this) {
            count = newcount;
        }
        return this;
    }

    public synchronized StringBuffer append (char str [], int offset, int len) {
        synchronized (value) {
            int newcount = count + len;
            if (newcount > value.length) expandCapacity (newcount);

            System.arraycopy (str, offset, value, count, len);
            count = newcount;
        }
        return this;
    }

    public StringBuffer append (boolean b) {
        if (b) {
            int newcount = count + 4;
            if (newcount > value.length) expandCapacity (newcount);

            value [count ++] = 't';
            value [count ++] = 'r';
            value [count ++] = 'u';
            value [count ++] = 'e';
        } else {
            int newcount = count + 5;
            if (newcount > value.length) synchronized (this) {
                expandCapacity (newcount);
            }

            value [count ++] = 'f';
            value [count ++] = 'a';
            value [count ++] = 'l';
            value [count ++] = 's';
            value [count ++] = 'e';
        }
        return this;
    }

    public synchronized StringBuffer append (char c) {
        int newcount = count + 1;
        if (newcount > value.length) expandCapacity (newcount);

        synchronized (value) {
            value [count ++] = c;
        }
        return this;
    }

    public StringBuffer delete (int start, int end) {
        if (start < 0) throw new StringIndexOutOfBoundsException (start);

        if (end > count) end = count;

        if (start > end) throw new StringIndexOutOfBoundsException ();

        int len = end - start;
        if (len > 0) {
            if (shared) copy ();

            System.arraycopy (value, start + len, value, start, count - end);
            count -= len;
        }
        return this;
    }

    public synchronized StringBuffer deleteCharAt (int index) {
        if ((index < 0) || (index >= count)) throw new StringIndexOutOfBoundsException ();

        if (shared) copy ();

        System.arraycopy (value, index + 1, value, index, count - index - 1);
        count --;
        return this;
    }

    public synchronized StringBuffer replace (int start, int end, String str) {
        if (start < 0) throw new StringIndexOutOfBoundsException (start);

        if (end > count) end = count;

        if (start > end) throw new StringIndexOutOfBoundsException ();

        int len = str.length ();
        int newCount = count + len - (end - start);
        if (newCount > value.length) expandCapacity (newCount);
        else if (shared) copy ();

        System.arraycopy (value, end, value, start + len, count - end);
        str.getChars (0, len, value, start);
        count = newCount;
        return this;
    }

    public synchronized String substring (int start) {
        /* MUTANT : "ASAT (Added Sync Around Statement)" */
        synchronized (this) {
            return substring (start, count);
            }
            /* MUTANT : "ASAT (Added Sync Around Statement)" */
        }

        public synchronized CharSequence subSequence (int start, int end) {
            synchronized (value) {
                return this.substring (start, end);
            }
        }

        public synchronized String substring (int start, int end) {
            if (start < 0) throw new StringIndexOutOfBoundsException (start);

            if (end > count) throw new StringIndexOutOfBoundsException (end);

            if (start > end) throw new StringIndexOutOfBoundsException (end - start);

            return new String (value, start, end - start);
        }

        public synchronized StringBuffer insert (int index, char str [], int offset, int len) {
            if ((index < 0) || (index > count)) throw new StringIndexOutOfBoundsException ();

            if ((offset < 0) || (offset + len < 0) || (offset + len > str.length)) throw new StringIndexOutOfBoundsException (
              offset);

            if (len < 0) throw new StringIndexOutOfBoundsException (len);

            int newCount = count + len;
            synchronized (this) {
                if (newCount > value.length) expandCapacity (newCount);
                else if (shared) copy ();

            }
            System.arraycopy (value, index, value, index + len, count - index);
            System.arraycopy (str, offset, value, index, len);
            count = newCount;
            return this;
        }

        public synchronized StringBuffer insert (int offset, Object obj) {
            return insert (offset, String.valueOf (obj));
        }

        public synchronized StringBuffer insert (int offset, String str) {
            if ((offset < 0) || (offset > count)) {
                synchronized (this) {
                    throw new StringIndexOutOfBoundsException ();
                }
            }
            if (str == null) {
                synchronized (this) {
                    str = String.valueOf (str);
                }
            }
            int len = str.length ();
            int newcount = count + len;
            if (newcount > value.length) expandCapacity (newcount);
            else if (shared) copy ();

            System.arraycopy (value, offset, value, offset + len, count - offset);
            str.getChars (0, len, value, offset);
            count = newcount;
            return this;
        }

        public synchronized StringBuffer insert (int offset, char str []) {
            if ((offset < 0) || (offset > count)) {
                throw new StringIndexOutOfBoundsException ();
            }
            int len = str.length;
            int newcount = count + len;
            if (newcount > value.length) expandCapacity (newcount);
            else if (shared) copy ();

            System.arraycopy (value, offset, value, offset + len, count - offset);
            System.arraycopy (str, 0, value, offset, len);
            count = newcount;
            return this;
        }

        public StringBuffer insert (int offset, boolean b) {
            return insert (offset, String.valueOf (b));
        }

        public synchronized StringBuffer insert (int offset, char c) {
            int newcount = count + 1;
            if (newcount > value.length) expandCapacity (newcount);
            else if (shared) copy ();

            System.arraycopy (value, offset, value, offset + 1, count - offset);
            synchronized (this) {
            }
            value [offset] = c;
            count = newcount;
            return this;
        }

        public StringBuffer insert (int offset, int i) {
            return insert (offset, String.valueOf (i));
        }

        public StringBuffer insert (int offset, long l) {
            return insert (offset, String.valueOf (l));
        }

        public synchronized StringBuffer insert (int offset, float f) {
            return insert (offset, String.valueOf (f));
        }

        public StringBuffer insert (int offset, double d) {
            return insert (offset, String.valueOf (d));
        }

        public synchronized StringBuffer reverse () {
            if (shared) copy ();

            int n = count - 1;
            for (int j = (n - 1) >> 1;
            j >= 0; -- j) synchronized (this) {
                {
                    char temp = value [j];
                    value [j] = value [n - j];
                    value [n - j] = temp;
                }}

            return this;
        }

        public synchronized String toString () {
            return new String (value);
        }

        final void setShared () {
            shared = true;
        }

        final char [] getValue () {
            return value;
        }

        private synchronized void readObject (java.io.ObjectInputStream s) throws java.io.IOException, ClassNotFoundException {
            s.defaultReadObject ();
            value = (char []) value.clone ();
            shared = false;
        }

    }


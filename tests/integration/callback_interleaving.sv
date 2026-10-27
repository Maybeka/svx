package callback_interleaving_pkg;
  class Base;
    virtual task work(int tag);
      int result;
      if (tag == 1) #3ns;
      else #10ns;
      result = check(tag);
      if (result != tag + 10) $fatal(1, "nested function callback failed");
    endtask
    virtual function int check(int tag);
      return tag;
    endfunction
  endclass
endpackage

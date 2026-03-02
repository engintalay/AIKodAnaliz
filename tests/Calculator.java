/**
 * Example Calculator Class - Test dosyası
 */
public class Calculator {
    
    /**
     * Main entry point
     */
    public static void main(String[] args) {
        Calculator calc = new Calculator();
        int result = calc.add(5, 3);
        System.out.println("5 + 3 = " + result);
    }
    
    /**
     * İki sayıyı toplar
     * @param a İlk sayı
     * @param b İkinci sayı
     * @return Toplam
     */
    public int add(int a, int b) {
        return a + b;
    }
    
    /**
     * İki sayıyı çıkar
     * @param a İlk sayı
     * @param b İkinci sayı
     * @return Fark
     */
    public int subtract(int a, int b) {
        return a - b;
    }
    
    /**
     * İki sayıyı çarpar
     * @param a İlk sayı
     * @param b İkinci sayı
     * @return Çarpım
     */
    public int multiply(int a, int b) {
        return a * b;
    }
    
    /**
     * İki sayıyı böler
     * @param a Bölünen
     * @param b Bölen
     * @return Bölüm
     */
    public double divide(int a, int b) {
        if (b == 0) {
            throw new IllegalArgumentException("Bölen sıfır olamaz");
        }
        return (double) a / b;
    }
}
